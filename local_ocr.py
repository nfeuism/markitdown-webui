"""Local image OCR integration for MarkItDown on Apple Silicon."""

from __future__ import annotations

import importlib.util
import os
import platform
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, BinaryIO

from markitdown import DocumentConverter, DocumentConverterResult, StreamInfo

DEFAULT_MODEL = "sahilchachra/unlimited-ocr-4bit-mlx"
DEFAULT_PROMPT = "<image>document parsing."
OCR_ENGINES = {"auto", "unlimited", "tesseract"}
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"}
IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
}


def _mlx_supported() -> bool:
    return (
        platform.system() == "Darwin"
        and platform.machine() == "arm64"
        and importlib.util.find_spec("mlx_vlm") is not None
    )


def _model_cache_path(model_id: str) -> Path:
    hub_home = Path(
        os.getenv(
            "HF_HOME",
            Path.home() / ".cache" / "huggingface",
        )
    ) / "hub"
    return hub_home / f"models--{model_id.replace('/', '--')}"


def get_ocr_capabilities() -> dict[str, Any]:
    model_id = os.getenv("MARKITDOWN_OCR_MODEL", DEFAULT_MODEL)
    unlimited_available = _mlx_supported()
    tesseract_available = shutil.which("tesseract") is not None
    return {
        "available": unlimited_available or tesseract_available,
        "default_engine": "auto",
        "unlimited_available": unlimited_available,
        "tesseract_available": tesseract_available,
        "model_id": model_id,
        "model_cached": _model_cache_path(model_id).exists(),
        "local_only": True,
    }


@lru_cache(maxsize=1)
def _load_unlimited_ocr() -> tuple[Any, Any, Any]:
    if not _mlx_supported():
        raise RuntimeError(
            "Unlimited-OCR requires macOS on Apple Silicon and the mlx-vlm package. "
            "Run ./install.sh on the Mac to install local OCR dependencies."
        )

    from mlx_vlm import generate, load

    model_id = os.getenv("MARKITDOWN_OCR_MODEL", DEFAULT_MODEL)
    model, processor = load(model_id)
    return model, processor, generate


def _gpt2_byte_decoder() -> dict[str, int]:
    byte_values = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(ord("¡"), ord("¬") + 1))
        + list(range(ord("®"), ord("ÿ") + 1))
    )
    code_points = byte_values[:]
    offset = 0
    for value in range(256):
        if value not in byte_values:
            byte_values.append(value)
            code_points.append(256 + offset)
            offset += 1
    return {chr(code_point): value for value, code_point in zip(byte_values, code_points)}


def _decode_byte_level_text(text: str) -> str:
    if "Ġ" not in text and "Ċ" not in text:
        return text
    reverse_map = _gpt2_byte_decoder()
    output = bytearray()
    for character in text:
        byte_value = reverse_map.get(character)
        if byte_value is None:
            output.extend(character.encode("utf-8"))
        else:
            output.append(byte_value)
    return output.decode("utf-8", errors="replace")


def clean_unlimited_output(text: str) -> str:
    """Repair MLX byte tokens and turn grounding titles into Markdown."""
    text = _decode_byte_level_text(text)
    box_pattern = re.compile(
        r"<\|det\|>(?P<kind>\w+)\s+\[[^\]]+\]<\|/det\|>"
    )

    def replace_box(match: re.Match[str]) -> str:
        return "# " if match.group("kind").lower() == "title" else ""

    text = box_pattern.sub(replace_box, text)
    text = re.sub(r"<\|[^|]+\|>", "", text)
    return text.strip()


def _run_unlimited_ocr(image_path: str) -> str:
    model, processor, generate = _load_unlimited_ocr()
    result = generate(
        model,
        processor,
        prompt=os.getenv("MARKITDOWN_OCR_PROMPT", DEFAULT_PROMPT),
        image=image_path,
        max_tokens=int(os.getenv("MARKITDOWN_OCR_MAX_TOKENS", "4096")),
        verbose=False,
    )
    return clean_unlimited_output(result.text)


def _run_tesseract(image_path: str) -> str:
    executable = shutil.which("tesseract")
    if executable is None:
        raise RuntimeError(
            "Tesseract is not installed. On macOS run: brew install tesseract"
        )
    completed = subprocess.run(
        [
            executable,
            image_path,
            "stdout",
            "-l",
            os.getenv("MARKITDOWN_TESSERACT_LANG", "chi_sim+eng"),
            "--oem",
            "1",
            "--psm",
            os.getenv("MARKITDOWN_TESSERACT_PSM", "6"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _stream_extension(stream_info: StreamInfo) -> str:
    extension = (stream_info.extension or "").lower().lstrip(".")
    if extension in IMAGE_EXTENSIONS:
        return extension
    filename = stream_info.filename or stream_info.local_path or ""
    return Path(filename).suffix.lower().lstrip(".")


class LocalOcrImageConverter(DocumentConverter):
    """MarkItDown converter backed by Unlimited-OCR and Tesseract."""

    def __init__(self, engine: str = "auto") -> None:
        if engine not in OCR_ENGINES:
            raise ValueError(f"Unsupported OCR engine: {engine}")
        self.engine = engine
        self.last_engine: str | None = None

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        return (
            _stream_extension(stream_info) in IMAGE_EXTENSIONS
            or (stream_info.mimetype or "").lower() in IMAGE_MIME_TYPES
        )

    def _convert_path(self, image_path: str) -> str:
        if self.engine == "unlimited":
            self.last_engine = "Unlimited-OCR (MLX Int4)"
            return _run_unlimited_ocr(image_path)
        if self.engine == "tesseract":
            self.last_engine = "Tesseract (chi_sim+eng)"
            return _run_tesseract(image_path)

        try:
            markdown = _run_unlimited_ocr(image_path)
            self.last_engine = "Unlimited-OCR (MLX Int4)"
            return markdown
        except Exception as unlimited_error:
            try:
                markdown = _run_tesseract(image_path)
                self.last_engine = "Tesseract fallback"
                return markdown
            except Exception as tesseract_error:
                raise RuntimeError(
                    "Neither Unlimited-OCR nor Tesseract could process the image. "
                    f"Unlimited-OCR: {unlimited_error}; Tesseract: {tesseract_error}"
                ) from tesseract_error

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> DocumentConverterResult:
        local_path = stream_info.local_path
        temp_path = ""
        try:
            if local_path and os.path.isfile(local_path):
                image_path = local_path
            else:
                suffix = f".{_stream_extension(stream_info) or 'png'}"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                    temp_path = temp_file.name
                    shutil.copyfileobj(file_stream, temp_file)
                image_path = temp_path

            markdown = self._convert_path(image_path).strip()
            if not markdown:
                raise RuntimeError("Local OCR returned empty output")
            return DocumentConverterResult(markdown=markdown)
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass


__all__ = [
    "IMAGE_EXTENSIONS",
    "LocalOcrImageConverter",
    "OCR_ENGINES",
    "clean_unlimited_output",
    "get_ocr_capabilities",
]

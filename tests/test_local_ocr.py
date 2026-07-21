import unittest
from unittest.mock import patch

from local_ocr import LocalOcrImageConverter, clean_unlimited_output


class LocalOcrTests(unittest.TestCase):
    def test_cleans_byte_level_tokens_and_grounding_boxes(self):
        raw = (
            "Ċ<|det|>titleĠ[47,Ġ92,Ġ403,Ġ214]<|/det|>"
            "æľ¬åľ°OCRæµĭè¯ķ"
        )
        self.assertEqual(clean_unlimited_output(raw), "# 本地OCR测试")

    def test_auto_falls_back_to_tesseract(self):
        converter = LocalOcrImageConverter(engine="auto")
        with patch("local_ocr._run_unlimited_ocr", side_effect=RuntimeError("no model")):
            with patch("local_ocr._run_tesseract", return_value="fallback text"):
                self.assertEqual(converter._convert_path("image.png"), "fallback text")
        self.assertEqual(converter.last_engine, "Tesseract fallback")

    def test_rejects_unknown_engine(self):
        with self.assertRaises(ValueError):
            LocalOcrImageConverter(engine="unknown")


if __name__ == "__main__":
    unittest.main()

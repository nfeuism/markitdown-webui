# MarkItDown Web UI

A modern web interface for Microsoft's MarkItDown document conversion tool.

## 🚀 Live Demo

**https://markitdown-webui-fawn.vercel.app/**

> The hosted demo converts documents. Local image OCR runs only in a local
> installation because the model executes on your Mac.

## Local OCR WebUI on Apple Silicon: Quick Start

This is the recommended installation for an M-series Mac. It installs the
WebUI as a private local service, adds the MLX Int4 build of Unlimited-OCR, and
uses Tesseract as a lightweight fallback. Images stay on your Mac and no API
key is required.

### 1. Install system prerequisites

```bash
brew install python@3.12 tesseract tesseract-lang
```

`tesseract-lang` provides Chinese and other additional language data. English
is included with the base `tesseract` package.

### 2. Clone and install

```bash
git clone https://github.com/nfeuism/markitdown-webui.git
cd markitdown-webui
MAX_FILE_SIZE_MB=500 ./install.sh
```

The installer creates an isolated Python environment, installs the local OCR
dependencies, copies the runtime to macOS Application Support, and starts a
LaunchAgent that automatically comes back after login or a crash.

### 3. Open the WebUI

```bash
open http://localhost:5001
```

Then:

1. Drag a JPG, PNG, WebP, BMP, or TIFF image into the upload area.
2. Leave **OCR engine** set to **Auto** for the recommended behavior.
3. Wait for the preview, then select **Download Markdown**.

The first Unlimited-OCR conversion downloads the approximately 2.35 GB
[`sahilchachra/unlimited-ocr-4bit-mlx`](https://huggingface.co/sahilchachra/unlimited-ocr-4bit-mlx)
model. Later conversions reuse the local cache. **Auto** tries Unlimited-OCR
first and switches to Tesseract if the model cannot run.

### 4. Check or update the installation

```bash
./status.sh
curl http://localhost:5001/api/ocr-capabilities

# Upgrade after new releases or configuration changes:
git pull
./install.sh
```

The service binds to `127.0.0.1`, so it is not exposed to your LAN or the
internet. See [macOS service controls](#macos-run-as-a-background-service-auto-start-at-login)
for stop, restart, and uninstall commands.

## Features

- **Drag & Drop Upload**: Intuitive file upload with drag-and-drop support
- **Document Conversion**: Convert PDF, Word, PowerPoint, Excel files
- **Web Content**: Convert HTML and web pages to Markdown
- **Data Formats**: Support for CSV, JSON, XML conversion
- **Live Preview**: See a preview of your converted Markdown before downloading
- **Modern UI**: Clean, responsive interface built with Tailwind CSS
- **Error Handling**: Comprehensive error reporting and validation
- **File Management**: Automatic cleanup of temporary files
- **Local Image OCR**: Convert screenshots and scanned images with Unlimited-OCR on Apple Silicon
- **Offline Fallback**: Use Tesseract for fast, low-memory Chinese and English OCR

## Supported File Formats

- **Documents**: PDF, DOCX, DOC, PPTX, PPT, XLSX, XLS
- **Web**: HTML, HTM
- **Data**: CSV, JSON, XML
- **Text**: TXT, MD
- **Images**: JPG, JPEG, PNG, WebP, BMP, TIFF (local OCR installation)

## Manual / Cross-platform Installation

Use this path for document conversion on Linux, Windows, or a Mac where you do
not want the managed background service. Apple Silicon users who want image
OCR should use the [quick start above](#local-ocr-webui-on-apple-silicon-quick-start).

1. Clone the repository:
   ```bash
   git clone https://github.com/nfeuism/markitdown-webui.git
   cd markitdown-webui
   ```

2. Create a virtual environment and install dependencies **into it**:

   **macOS / Linux:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   **Windows (PowerShell):**
   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Run the application (inside the activated venv):
   ```bash
   python app.py
   ```

4. Open your browser and navigate to `http://localhost:5001`

> ### ⚠️ macOS: `zsh: command not found: pip` (and why `python app.py` fails too)
>
> On a modern Mac the bare `pip` and `python` commands **do not exist** — Apple
> and Homebrew ship them as `pip3` / `python3`. So the classic
> `pip install -r requirements.txt` gives:
> ```
> zsh: command not found: pip
> ```
> And even `pip3 install -r requirements.txt` usually fails with an
> **`error: externally-managed-environment`** ([PEP 668](https://peps.python.org/pep-0668/)),
> because Homebrew / python.org Python refuse to let you install packages into
> the system Python.
>
> **Fix: always install into a virtual environment** (step 2 above). Once the
> venv is activated, `pip` and `python` exist and point at the venv, so every
> command in this README works verbatim — no `pip3`/`python3` juggling, no
> PEP 668 error.
>
> **Faster alternative with [uv](https://github.com/astral-sh/uv):**
> ```bash
> uv venv --python 3.11 .venv
> uv pip install --python .venv/bin/python -r requirements.txt   # uv-made venvs have no pip; use `uv pip`
> .venv/bin/python app.py
> ```
>
> **Or skip all of this on macOS** and let [`./install.sh`](#macos-run-as-a-background-service-auto-start-at-login)
> build the venv, install everything, and run the app as a background service
> for you (see the next section).

## macOS: Run as a Background Service (auto-start at login)

On macOS you can run the Web UI as a managed **launchd** service so it starts
automatically at login and restarts itself if it crashes — no need to launch it
manually or keep a terminal open.

```bash
# From the repo folder — creates the .venv, installs deps, generates a
# per-user LaunchAgent, and starts the service:
./install.sh
```

That's it. The UI is now always available at `http://localhost:5001` and comes
back on every reboot.

On Apple Silicon, the installer also adds `mlx-vlm` for the local
`sahilchachra/unlimited-ocr-4bit-mlx` model. The model is downloaded lazily on
the first image conversion (about 2.35 GB) and then reused from the local
Hugging Face cache. No API key is required. The Web UI offers:

- **Auto**: Unlimited-OCR first, then Tesseract if the model fails.
- **Unlimited-OCR**: layout-aware local OCR using MLX Int4.
- **Tesseract**: faster and lighter plain-text OCR.

For the Tesseract fallback on macOS:

```bash
brew install tesseract tesseract-lang
```

To skip MLX dependencies during a local installation:

```bash
INSTALL_LOCAL_OCR=0 ./install.sh
```

### One-click control scripts

| Command | What it does |
|---------|--------------|
| `./install.sh`  | Install/repair the service + auto-start (idempotent). |
| `./start.sh`    | Start now. |
| `./stop.sh`     | Stop now (still auto-starts again at next login). |
| `./restart.sh`  | Restart the running server. |
| `./status.sh`   | Show launchd state, port, and HTTP health. |
| `./uninstall.sh`| Remove auto-start (deletes the LaunchAgent). Repo/venv untouched. |

Details and internals are documented in [`CONTROL.md`](CONTROL.md).

- Runs `serve.py` (local service entry point: no Flask debug-reloader, binds
  `127.0.0.1` only) instead of `app.py`.
- Logs to `~/Library/Application Support/MarkItDownWebUI/logs/webui.log`.
- To change the port: `PORT=5055 ./install.sh`.

## Usage

1. **Upload a file**: Drag and drop a file onto the upload area or click "Browse Files".
2. **Choose OCR for images**: Auto is recommended; select Unlimited-OCR or Tesseract when you need to force one engine.
3. **Wait for conversion**: The file is converted locally to Markdown.
4. **Preview the result**: Review the extracted text in the browser.
5. **Download**: Click "Download Markdown" to save the converted file.

## Configuration

- **Maximum file size**: 500 MB by default for local use (configure with `MAX_FILE_SIZE_MB`)
- **Supported formats**: Defined in `ALLOWED_EXTENSIONS` in `app.py`
- **Cleanup interval**: Files older than 1 hour are automatically deleted
- **Port**: Application runs on port 5001
- **OCR model**: `MARKITDOWN_OCR_MODEL` (defaults to the MLX Int4 Unlimited-OCR model)
- **OCR output limit**: `MARKITDOWN_OCR_MAX_TOKENS` (defaults to 4096)

### Mac mini local large-file setup

The recommended large-file deployment is the included macOS LaunchAgent. It
binds to `127.0.0.1`, so the UI is available only on the Mac at
`http://localhost:5001` and is not exposed to the LAN or internet.

```bash
MAX_FILE_SIZE_MB=500 ./install.sh
```

The setting is persisted in the generated LaunchAgent plist. Re-run the same
command with another positive integer to change the limit. The application
accepts one conversion at a time to avoid exhausting memory, and files older
than one hour are removed by the cleanup endpoint.

The installer syncs a runtime copy to
`~/Library/Application Support/MarkItDownWebUI`. This avoids macOS privacy
restrictions that can prevent a LaunchAgent from reading a checkout under
Desktop or Documents. Re-run `./install.sh` after pulling new source code.

> The Vercel deployment remains subject to Vercel Functions' request-body
> limit. Increasing `MAX_FILE_SIZE_MB` does not bypass the hosting platform's
> limit; use the local LaunchAgent setup for large files.

## Requirements

- Python 3.10 or higher
- MarkItDown library with all dependencies
- Flask web framework

## API Endpoints

- `GET /`: Main web interface
- `POST /convert`: Convert uploaded file to Markdown
- `GET /download/<filename>`: Download converted file
- `POST /cleanup`: Clean up old temporary files
- `GET /api/ocr-capabilities`: Report local model and Tesseract availability

## Error Handling

The application includes comprehensive error handling for:
- Invalid file formats
- File size limits
- Conversion failures
- Network errors
- File system errors

## Security Features

- File type validation
- Secure filename handling
- Automatic cleanup of temporary files
- File size limits
- Input sanitization

## Troubleshooting

### `command not found: pip` / `externally-managed-environment`
You're not inside a virtual environment. See the **macOS pip note** in the
[Installation](#installation) section — create and activate a `.venv` first,
then `pip` works.

### PDF / Office Conversion Issues
If a conversion fails with a `MissingDependencyException` (e.g. for `.xlsx`,
`.pptx`, `.docx`, or `.pdf`), the format's optional dependency isn't installed
**in the venv the app runs from**. Reinstall the full dependency set into that
venv:
```bash
source .venv/bin/activate          # make sure you're in the app's venv
pip install --force-reinstall -r requirements.txt   # requirements pins markitdown[all]
```
Notes:
- `requirements.txt` already requests `markitdown[all]`, which pulls in
  `openpyxl` (xlsx), `python-pptx` (pptx), `mammoth` (docx), `pdfminer-six` /
  `pdfplumber` (pdf), etc.
- A **separate** `markitdown` CLI you may have installed elsewhere (e.g.
  `uv tool install markitdown`) has its **own** environment — upgrading it does
  **not** affect this web app's venv. Always install extras into `.venv`.
- After installing new dependencies, **restart** the app (or `./restart.sh` if
  running as the launchd service) so the new packages are loaded.

### Local OCR is unavailable

Check what the running service can see:

```bash
curl http://localhost:5001/api/ocr-capabilities
```

- On Apple Silicon, run `./install.sh` again to install or repair `mlx-vlm`.
- Install the Tesseract fallback with
  `brew install tesseract tesseract-lang`, then run `./restart.sh`.
- If `model_cached` is `false`, select Unlimited-OCR once and allow the first
  model download to finish. Check that several GB of disk space is available.
- If one engine returns poor text for a particular image, choose the other
  engine explicitly in the WebUI.

Service logs are stored at:

```text
~/Library/Application Support/MarkItDownWebUI/logs/webui.log
```

### Port Already in Use
If port 5001 is already in use:
```bash
# Install or move the managed service to another local port:
PORT=5055 ./install.sh
open http://localhost:5055
```

## License

This project is built using Microsoft's MarkItDown library. Please refer to the original MarkItDown license for usage terms.

## Contributing

Feel free to submit issues and enhancement requests!

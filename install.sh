#!/usr/bin/env bash
# Install MarkItDown Web UI as a macOS background service (auto-start at login).
# Idempotent: safe to re-run. Generates a per-user launchd LaunchAgent that points
# at THIS checkout, then loads it. Works for any user / any clone location.
set -euo pipefail
unset PYTHONPATH 2>/dev/null || true

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# LaunchAgents can be denied access to Desktop/Documents by macOS privacy
# controls even when the interactive terminal can read them. Run a synced copy
# from Application Support, which is intended for per-user background services.
DIR="${MARKITDOWN_APP_DIR:-$HOME/Library/Application Support/MarkItDownWebUI}"
LABEL="com.$(id -un).markitdown-webui"
DOMAIN="gui/$(id -u)"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
PORT="${PORT:-5001}"
MAX_FILE_SIZE_MB="${MAX_FILE_SIZE_MB:-500}"
CLEANUP_AGE_HOURS="${CLEANUP_AGE_HOURS:-1}"
INSTALL_LOCAL_OCR="${INSTALL_LOCAL_OCR:-1}"
MARKITDOWN_OCR_MODEL="${MARKITDOWN_OCR_MODEL:-sahilchachra/unlimited-ocr-4bit-mlx}"
MARKITDOWN_OCR_MAX_TOKENS="${MARKITDOWN_OCR_MAX_TOKENS:-4096}"
HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
PY="$DIR/.venv/bin/python"

if command -v brew >/dev/null 2>&1; then
    HOMEBREW_PREFIX="$(brew --prefix)"
else
    HOMEBREW_PREFIX="/opt/homebrew"
fi
SERVICE_PATH="$DIR/.venv/bin:$HOMEBREW_PREFIX/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "==> Source: $SOURCE_DIR"
echo "==> Runtime: $DIR"
echo "==> Label: $LABEL"
echo "==> Port:  $PORT"
echo "==> Maximum file size: ${MAX_FILE_SIZE_MB} MB"

# 1. Sync the runtime copy ------------------------------------------------------
mkdir -p "$DIR"
if [ "$SOURCE_DIR" != "$DIR" ]; then
    echo "==> Syncing application into macOS Application Support ..."
    rsync -a --delete \
        --exclude '.git/' \
        --exclude '.venv/' \
        --exclude 'logs/' \
        --exclude 'uploads/' \
        "$SOURCE_DIR/" "$DIR/"
fi

# 2. Ensure venv + dependencies -------------------------------------------------
if [ ! -x "$PY" ]; then
    echo "==> Creating .venv ..."
    if command -v uv >/dev/null 2>&1; then
        uv venv --python 3.12 "$DIR/.venv"
    else
        python3 -m venv "$DIR/.venv"
    fi
fi
echo "==> Installing dependencies ..."
if command -v uv >/dev/null 2>&1; then
    # uv-created venvs have no pip; uv pip installs straight into the target venv
    uv pip install --python "$PY" -q -r "$DIR/requirements.txt"
else
    "$PY" -m pip install -q --upgrade pip
    "$PY" -m pip install -q -r "$DIR/requirements.txt"
fi
if [ "$INSTALL_LOCAL_OCR" = "1" ] && [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    echo "==> Installing Apple Silicon local OCR dependencies ..."
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python "$PY" -q -r "$DIR/requirements-local-ocr.txt"
    else
        "$PY" -m pip install -q -r "$DIR/requirements-local-ocr.txt"
    fi
    if command -v tesseract >/dev/null 2>&1; then
        echo "==> Tesseract fallback: ready"
    else
        echo "⚠️  Tesseract fallback not found; install with: brew install tesseract"
    fi
fi
mkdir -p "$DIR/logs"

# 3. Generate the LaunchAgent plist --------------------------------------------
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${DIR}/.venv/bin/python</string>
        <string>${DIR}/serve.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${SERVICE_PATH}</string>
        <key>PORT</key>
        <string>${PORT}</string>
        <key>MAX_FILE_SIZE_MB</key>
        <string>${MAX_FILE_SIZE_MB}</string>
        <key>CLEANUP_AGE_HOURS</key>
        <string>${CLEANUP_AGE_HOURS}</string>
        <key>MARKITDOWN_OCR_MODEL</key>
        <string>${MARKITDOWN_OCR_MODEL}</string>
        <key>MARKITDOWN_OCR_MAX_TOKENS</key>
        <string>${MARKITDOWN_OCR_MAX_TOKENS}</string>
        <key>HF_HOME</key>
        <string>${HF_HOME}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardOutPath</key>
    <string>${DIR}/logs/webui.log</string>
    <key>StandardErrorPath</key>
    <string>${DIR}/logs/webui.log</string>
</dict>
</plist>
PLIST_EOF

plutil -lint "$PLIST" >/dev/null

# 4. (Re)load the agent ---------------------------------------------------------
if launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
    launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
    # bootout is asynchronous — wait for launchd to fully drop the job,
    # otherwise the following bootstrap hits "Input/output error 5".
    for _ in $(seq 1 20); do
        launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1 || break
        sleep 0.3
    done
fi
launchctl enable "${DOMAIN}/${LABEL}" 2>/dev/null || true
if ! launchctl bootstrap "${DOMAIN}" "${PLIST}" 2>/dev/null; then
    sleep 1
    launchctl bootstrap "${DOMAIN}" "${PLIST}"   # retry once on transient error
fi

# 5. Health check ---------------------------------------------------------------
URL="http://localhost:${PORT}"
for _ in $(seq 1 120); do
    if curl -s -o /dev/null "${URL}/" 2>/dev/null; then
        echo "✅ Installed and running — auto-starts at every login: ${URL}"
        echo "   Control: ./start.sh ./stop.sh ./restart.sh ./status.sh ./uninstall.sh"
        exit 0
    fi
    sleep 0.5
done
echo "⚠️  Installed but not responding yet — check ${DIR}/logs/webui.log"
exit 1

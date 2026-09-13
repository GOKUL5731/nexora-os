#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

ROOT="$PWD"
APP_DIR="$ROOT/nexora_os"
FRONTEND_DIR="$APP_DIR/frontend"
VENV_DIR="$ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  source "$ROOT/.env"
  set +a
  echo "[OK] Loaded local .env configuration."
fi

if [[ -n "${LIVEKIT_URL:-}" && -n "${LIVEKIT_API_KEY:-}" && -n "${LIVEKIT_API_SECRET:-}" ]]; then
  echo "[OK] LiveKit realtime transport configured."
else
  echo "[INFO] LiveKit disabled: configure LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET in .env."
fi

command -v python3 >/dev/null || { echo "Python 3.10+ is required."; exit 1; }
command -v npm >/dev/null || { echo "Node.js and npm are required."; exit 1; }
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  python3 --version
  echo "Python 3.10+ is required."
  exit 1
}

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[INFO] Creating virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

if ! "$PYTHON_BIN" -c 'import fastapi, uvicorn, pydantic, psutil, PIL, cv2, speech_recognition, pyaudio, pyttsx3, pytesseract, pyautogui, mss' >/dev/null 2>&1; then
  echo "[INFO] Installing or repairing backend dependencies"
  "$PYTHON_BIN" -m pip install -r "$APP_DIR/requirements.txt"
fi

if ! "$PYTHON_BIN" -c 'from PySide6.QtWebEngineWidgets import QWebEngineView' >/dev/null 2>&1; then
  echo "[INFO] Installing desktop runtime"
  "$PYTHON_BIN" -m pip install -r "$APP_DIR/requirements-desktop.txt"
fi

"$PYTHON_BIN" -m pip check

cd "$FRONTEND_DIR"
if [[ ! -d node_modules ]]; then
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
fi
npm run build

cd "$ROOT"
exec "$PYTHON_BIN" -m nexora_os.desktop_app

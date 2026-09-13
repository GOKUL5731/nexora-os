#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

ROOT="$PWD"
APP_DIR="$ROOT/nexora_os"
VENV_DIR="$ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"

command -v python3 >/dev/null || { echo "Python 3.10+ is required."; exit 1; }
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  python3 --version
  echo "Python 3.10+ is required."
  exit 1
}

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[INFO] Creating virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

if ! "$PYTHON_BIN" -c 'from PySide6.QtWidgets import QApplication' >/dev/null 2>&1; then
  echo "[INFO] Installing desktop runtime"
  "$PYTHON_BIN" -m pip install -r "$APP_DIR/requirements-desktop.txt"
fi

exec "$PYTHON_BIN" -m nexora_os.pet_app "$@"

#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
command -v python3 >/dev/null || { echo 'Python 3.10+ is required.'; exit 1; }
command -v npm >/dev/null || { echo 'Node.js and npm are required.'; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
[[ -d .venv ]] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r nexora_os/requirements.txt -r nexora_os/requirements-desktop.txt
cd nexora_os/frontend
[[ -d node_modules ]] || npm ci
npm run build
cd ../..
exec python -m nexora_os.desktop_app

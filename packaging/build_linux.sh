#!/usr/bin/env bash
# Local Linux build: PyInstaller onedir + tar.gz + nfpm deb.
set -euo pipefail
cd "$(dirname "$0")/.."
export APP_VERSION="${APP_VERSION:-0.0.0-dev}"

PY="${PYTHON:-python3}"
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; fi

printf '%s' "$APP_VERSION" > _version.txt

"$PY" -m PyInstaller packaging/nexadesk.spec --noconfirm --distpath dist --workpath build
tar -czf "dist/NexaDesk_${APP_VERSION}_linux_amd64.tar.gz" -C dist NexaDesk
NFPM="$(command -v nfpm || echo "$HOME/.local/bin/nfpm")"
"$NFPM" package --config packaging/nfpm.yaml --packager deb --target "dist/NexaDesk_${APP_VERSION}_amd64.deb"
echo "built: dist/NexaDesk/ + tar.gz + deb"

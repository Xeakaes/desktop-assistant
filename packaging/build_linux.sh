#!/usr/bin/env bash
# Local Linux build: PyInstaller onedir + tar.gz + nfpm deb.
set -euo pipefail
cd "$(dirname "$0")/.."
export APP_VERSION="${APP_VERSION:-0.0.0-dev}"
.venv/bin/pyinstaller packaging/desktop-assistant.spec --noconfirm --distpath dist --workpath build
tar -czf "dist/desktop-assistant_${APP_VERSION}_linux_amd64.tar.gz" -C dist desktop-assistant
NFPM="$(command -v nfpm || echo "$HOME/.local/bin/nfpm")"
"$NFPM" package --config packaging/nfpm.yaml --packager deb --target "dist/desktop-assistant_${APP_VERSION}_amd64.deb"
echo "built: dist/desktop-assistant/ + tar.gz + deb"

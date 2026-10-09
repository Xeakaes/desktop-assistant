#!/usr/bin/env bash
# Local Linux build: PyInstaller onedir (+ tar.gz; deb built separately via nfpm).
set -euo pipefail
cd "$(dirname "$0")/.."
export APP_VERSION="${APP_VERSION:-0.0.0-dev}"
.venv/bin/pyinstaller packaging/desktop-assistant.spec --noconfirm --distpath dist --workpath build
tar -czf "dist/desktop-assistant_${APP_VERSION}_linux_amd64.tar.gz" -C dist desktop-assistant
echo "built: dist/desktop-assistant/  + tar.gz"

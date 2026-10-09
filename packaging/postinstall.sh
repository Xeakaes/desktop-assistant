#!/bin/sh
# Refresh desktop database if available (best-effort).
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
exit 0

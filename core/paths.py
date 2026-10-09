"""Frozen-aware path resolution for config/data/assets (spec packaging §1)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def bundle_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", repo_root()))
    return repo_root()


def config_dir() -> Path:
    if is_frozen():
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", str(Path.home()))) / "desktop-assistant"
        else:
            base = Path.home() / ".config" / "desktop-assistant"
        return base
    return repo_root() / "config"


def data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home()))) / "desktop-assistant"
    else:
        base = Path.home() / ".local" / "share" / "desktop-assistant"
    base.mkdir(parents=True, exist_ok=True)
    return base


def assets_dir() -> Path:
    return bundle_root() / "assets"


def ensure_user_config() -> None:
    """Seed config_dir() with defaults on first frozen launch."""
    import json

    cfg = config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    settings = cfg / "settings.json"
    if not settings.exists():
        template = bundle_root() / "config_template" / "settings.json"
        if template.exists():
            settings.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            settings.write_text(
                json.dumps(
                    {
                        "avatar": "base",
                        "language": "tr",
                        "theme": "dark",
                        "screen_control": {"enabled": True, "host": "127.0.0.1", "port": 8745},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
    secrets = cfg / "secrets.json"
    if not secrets.exists():
        secrets.write_text("{}", encoding="utf-8")
        try:
            os.chmod(secrets, 0o600)
        except OSError:
            pass

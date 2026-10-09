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

"""Single source of truth for config file locations (spec §3)."""

from __future__ import annotations

import os
from pathlib import Path

from core.paths import config_dir

CONFIG_DIR: Path = config_dir()
SETTINGS_PATH: Path = CONFIG_DIR / "settings.json"
SECRETS_PATH: Path = CONFIG_DIR / "secrets.json"
UI_JSON_PATH: Path = CONFIG_DIR / "ui.json"


def ui_json_path() -> Path:
    """Env override wins (used by tests); default is config/ui.json."""
    env = os.environ.get("DESKTOP_ASSISTANT_UI_JSON")
    return Path(env) if env else UI_JSON_PATH

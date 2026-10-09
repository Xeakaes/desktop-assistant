"""Single source of truth for config file locations (spec §3)."""

from __future__ import annotations

import os
from pathlib import Path

from core.bootstrap import DEFAULT_SECRETS, DEFAULT_SETTINGS

CONFIG_DIR: Path = DEFAULT_SETTINGS.parent
SETTINGS_PATH: Path = DEFAULT_SETTINGS
SECRETS_PATH: Path = DEFAULT_SECRETS
UI_JSON_PATH: Path = CONFIG_DIR / "ui.json"


def ui_json_path() -> Path:
    """Env override wins (used by tests); default is config/ui.json."""
    env = os.environ.get("DESKTOP_ASSISTANT_UI_JSON")
    return Path(env) if env else UI_JSON_PATH

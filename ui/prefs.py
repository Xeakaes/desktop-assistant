"""config/ui.json preferences: mode / theme / language (spec §3, §6, §12)."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

MODES = ("gui", "avatar")
THEMES = ("dark", "light")


@dataclass(frozen=True)
class UiPrefs:
    mode: str | None
    theme: str
    lang: str


def _read_raw(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_raw(path: Path, data: dict) -> None:
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2).encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_prefs(path: Path) -> UiPrefs:
    defaults = UiPrefs(mode=None, theme="dark", lang="tr")
    if not path.exists():
        return defaults
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    mode = data.get("mode")
    if mode not in MODES:
        mode = None
    theme = data.get("theme")
    if theme not in THEMES:
        theme = defaults.theme
    lang = data.get("lang")
    if lang not in ("tr", "en"):
        lang = defaults.lang
    return UiPrefs(mode=mode, theme=theme, lang=lang)


def save_prefs(path: Path, prefs: UiPrefs) -> None:
    data = _read_raw(path)
    data.update({"mode": prefs.mode, "theme": prefs.theme, "lang": prefs.lang})
    _write_raw(path, data)


def load_avatar_pos(path: Path) -> tuple[int, int] | None:
    """Last saved avatar window position, if any."""
    pos = _read_raw(path).get("avatar_pos")
    if (
        isinstance(pos, list)
        and len(pos) == 2
        and all(isinstance(v, int) for v in pos)
    ):
        return pos[0], pos[1]
    return None


def save_avatar_pos(path: Path, x: int, y: int) -> None:
    data = _read_raw(path)
    data["avatar_pos"] = [int(x), int(y)]
    _write_raw(path, data)


def switch_mode(path: Path, mode: str) -> None:
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    prefs = load_prefs(path)
    save_prefs(path, replace(prefs, mode=mode))


def switch_theme(path: Path, theme: str) -> None:
    if theme not in THEMES:
        raise ValueError(f"unknown theme: {theme}")
    prefs = load_prefs(path)
    save_prefs(path, replace(prefs, theme=theme))


def switch_lang(path: Path, lang: str) -> None:
    if lang not in ("tr", "en"):
        raise ValueError(f"unknown language: {lang}")
    prefs = load_prefs(path)
    save_prefs(path, replace(prefs, lang=lang))


def restart_argv() -> list[str]:
    """Build a correct re-exec argv for the current launch mode.

    - python -m pkg.mod  -> [exe, -m, pkg.mod, *args]  (keeps -m; without it
      sys.path[0] becomes the module's directory and sibling packages break)
    - frozen (PyInstaller) -> [exe, *args]  (exe is the app itself)
    - python path/to/script.py -> [exe, path, *args]
    """
    import sys

    exe = sys.executable
    args = sys.argv[1:]
    if getattr(sys, "frozen", False):
        return [exe, *args]
    spec = getattr(sys.modules.get("__main__"), "__spec__", None)
    if spec is not None and spec.name:
        return [exe, "-m", spec.name, *args]
    return [exe, *sys.argv]


def restart_into(path: Path, mode: str) -> None:
    import os
    import sys

    switch_mode(path, mode)
    argv = restart_argv()
    os.execv(sys.executable, argv)

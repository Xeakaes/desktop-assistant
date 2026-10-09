"""Mode dispatcher: first-run chooser + GUI/Avatar launch (spec §6)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.bootstrap import DEFAULT_SETTINGS
from ui.chooser import ModeChooser
from ui.i18n import i18n
from ui.prefs import UiPrefs, load_prefs, save_prefs
from ui.theme import apply_theme

DEFAULT_UI_JSON = Path.home() / ".config" / "desktop-assistant" / "ui.json"


def _ui_json_path() -> Path:
    return Path(os.environ.get("DESKTOP_ASSISTANT_UI_JSON", str(DEFAULT_UI_JSON)))


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    ui_json = _ui_json_path()
    prefs = load_prefs(ui_json)
    i18n.set_language(prefs.lang)
    apply_theme(app, prefs.theme)
    mode = prefs.mode
    if mode is None:
        chooser = ModeChooser()
        if chooser.exec():
            mode = chooser.chosen or "gui"
            save_prefs(ui_json, UiPrefs(mode=mode, theme=prefs.theme, lang=prefs.lang))
        else:
            mode = "gui"
            save_prefs(ui_json, UiPrefs(mode=mode, theme=prefs.theme, lang=prefs.lang))
    if mode == "gui":
        from ui.gui.main_window import ChatWindow

        win = ChatWindow(ui_json_path=ui_json)
        win.show()
        code = app.exec()
    else:
        from ui.avatar_app import main as avatar_main

        code = avatar_main()
        os._exit(code)
    os._exit(code)
    return code


if __name__ == "__main__":
    sys.exit(main())

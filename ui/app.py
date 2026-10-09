"""Mode dispatcher: first-run chooser + GUI/Avatar launch (spec §6)."""

from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication

from core.bootstrap import build_runtime
from ui.bridge import QtBridge
from ui.chooser import ModeChooser
from ui.history import HistoryStore, default_db_path
from ui.i18n import i18n
from ui.paths import SETTINGS_PATH, SECRETS_PATH, ui_json_path
from ui.prefs import UiPrefs, load_prefs, save_prefs
from ui.theme import apply_theme


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    ui_json = ui_json_path()
    prefs = load_prefs(ui_json)
    i18n.set_language(prefs.lang)
    apply_theme(app, prefs.theme)
    mode = prefs.mode
    if mode is None:
        chooser = ModeChooser()
        if not chooser.exec() or not chooser.chosen:
            os._exit(0)
        mode = chooser.chosen
        save_prefs(ui_json, UiPrefs(mode=mode, theme=prefs.theme, lang=prefs.lang))
    if mode == "gui":
        from ui.gui.main_window import ChatWindow

        runtime, bus, _session = build_runtime()
        history = HistoryStore(default_db_path())
        win = ChatWindow(
            runtime=runtime,
            bus=bus,
            history=history,
            ui_json_path=ui_json,
            settings_path=SETTINGS_PATH,
            secrets_path=SECRETS_PATH,
        )
        try:
            from app_entry.entry import maybe_spawn_server
            from core.config import load_settings

            maybe_spawn_server(load_settings(SETTINGS_PATH))
        except Exception as exc:
            print(f"screen-control spawn skipped: {exc}", file=sys.stderr)
        app.aboutToQuit.connect(runtime.close)
        app.aboutToQuit.connect(history.close)
        win.show()
        code = app.exec()
        os._exit(code)
    else:
        from ui.avatar_app import main as avatar_main

        code = avatar_main()
        os._exit(code)
    return code


if __name__ == "__main__":
    sys.exit(main())

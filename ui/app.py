"""Mode dispatcher: first-run chooser + GUI/Avatar launch (spec §6)."""

from __future__ import annotations

import os
import sys

# Bootstrap: allow running as a plain script (python ui/app.py) where
# sys.path[0] is the ui/ directory, not the repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PySide6.QtWidgets import QApplication

from core.bootstrap import build_runtime
from core.paths import ensure_user_config
from ui.bridge import QtBridge
from ui.chooser import ModeChooser
from ui.fonts import load_fonts
from ui.history import HistoryStore, default_db_path
from ui.i18n import i18n
from ui.paths import SETTINGS_PATH, SECRETS_PATH, ui_json_path
from ui.prefs import UiPrefs, load_prefs, save_prefs
from ui.theme import apply_theme


def main() -> int:
    ensure_user_config()
    app = QApplication.instance() or QApplication(sys.argv)
    load_fonts(app)
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

"""M1 desktop entry: avatar + bubble + settings wired to the M0 agent runtime."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import os

# Bootstrap: allow running as a plain script (python ui/avatar_app.py) where
# sys.path[0] is the ui/ directory, not the repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMessageBox, QMenu

from core.bootstrap import build_runtime
from core.config import load_settings
from ui.avatar.state_machine import reduce_event
from ui.avatar.window import AvatarWindow
from ui.bridge import QtBridge
from ui.bubble import BubbleWindow
from ui.history import HistoryStore, default_db_path
from ui.i18n import i18n
from ui.paths import SECRETS_PATH, SETTINGS_PATH, ui_json_path
from ui.prefs import load_prefs, restart_into
from ui.settings import SettingsWindow
from ui.theme import apply_theme

from core.paths import assets_dir

ASSETS = assets_dir() / "avatars"


class _UiSignals(QObject):
    finished = Signal(str)
    activity = Signal(str)


class App:
    def __init__(self) -> None:
        self.settings_path = SETTINGS_PATH
        self.secrets_path = SECRETS_PATH
        self.runtime, self.bus, self.session = build_runtime()
        self._settings_cache = load_settings(self.settings_path)
        self._history = HistoryStore(default_db_path())
        self._history.purge_empty_sessions()
        self._sid: str | None = None  # created lazily on first send
        avatar_name = self._settings_cache.get("avatar", "base")
        self.avatar = self._make_avatar(avatar_name)
        self.bubble = BubbleWindow(on_send=self._on_send, on_cancel=self._on_cancel)
        self.settings_win = SettingsWindow(self.settings_path, self.secrets_path)
        self.bridge = QtBridge(self.bus)
        self.signals = _UiSignals()
        self.signals.finished.connect(self._on_finished)
        self.signals.activity.connect(self.bubble.set_tool_activity)
        self.bridge.sig.connect(self._on_event)
        try:
            from app_entry.entry import maybe_spawn_server

            maybe_spawn_server(self._settings_cache)
        except Exception as exc:
            print(f"screen-control spawn skipped: {exc}", file=sys.stderr)
        screen = QApplication.primaryScreen().geometry()
        self.avatar.move(screen.width() - 220, screen.height() - 260)
        self.avatar.show()
        self.bubble.move(max(0, self.avatar.x() - 340), max(0, self.avatar.y() - 80))
        if getattr(self, "_pending_avatar_note", ""):
            self.bubble.append_message("tool", self._pending_avatar_note)

    def _make_avatar(self, name: str) -> AvatarWindow:
        from core.paths import user_avatars_dir

        # User-built packs take precedence; then the bundled asset dir.
        for root in (user_avatars_dir(), ASSETS):
            candidate = root / name
            if candidate.is_dir():
                try:
                    return AvatarWindow(candidate, context_menu_factory=self.context_menu)
                except Exception:
                    continue
        if name != "base":
            self._pending_avatar_note = i18n.t("chat.avatar_fallback", name=name)
            return AvatarWindow(ASSETS / "base", context_menu_factory=self.context_menu)
        raise FileNotFoundError(f"avatar not found: {name}")

    def _on_send(self, text: str) -> None:
        self.bubble.append_message("user", text)
        if self._sid is None:
            self._sid = self._history.create_session()
        self._history.append(self._sid, "user", text)
        self.bubble.set_busy(True)
        threading.Thread(target=self._run_agent, args=(text,), daemon=True).start()

    def _run_agent(self, text: str) -> None:
        try:
            tid = self.runtime.begin_task(self._sid, text)
            self.runtime.run_task(tid)
        except Exception as exc:
            self.signals.finished.emit(f"{i18n.t('chat.error_prefix')}: {exc}")

    def _on_finished(self, final: str) -> None:
        self.bubble.set_busy(False)
        self.bubble.set_tool_activity("")

    def _on_cancel(self) -> None:
        self.runtime.cancel_active_task()

    def _on_event(self, event) -> None:
        new_state = reduce_event(self.avatar.current_state(), event.name)
        self.avatar.set_state(new_state)
        if event.name == "agent_started":
            self.bubble.setVisible(True)
            self.bubble.set_busy(True)
        elif event.name == "tool_started":
            name = event.payload.get("tool_name", "")
            self.signals.activity.emit(i18n.t("chat.activity_running", name=name))
            line = i18n.t("chat.tool_started_line", name=name)
            self.bubble.append_message("tool", line)
            self._history.append(self._sid, "tool", line, tool_name=name)
        elif event.name == "tool_finished":
            self.bubble.set_tool_activity("")
            name = event.payload.get("tool_name", "")
            ok = event.payload.get("ok", "")
            key = "chat.tool_finished_ok" if ok else "chat.tool_finished_fail"
            line = i18n.t(key, name=name)
            self.bubble.append_message("tool", line)
            self._history.append(self._sid, "tool", line, tool_name=name)
        elif event.name == "assistant_message":
            text = event.payload.get("text", "")
            if text:
                self.bubble.append_message("assistant", text)
                self._history.append(self._sid, "assistant", text)
        elif event.name == "agent_finished":
            self._on_finished("")
        elif event.name == "agent_error":
            self._on_finished("")
            msg = event.payload.get("message") or event.payload.get("error_code", "")
            code = event.payload.get("error_code", "")
            line = f"{i18n.t('chat.error_prefix')} ({code}): {msg}"
            self.bubble.append_message("assistant", line)
            self._history.append(self._sid, "assistant", line)
        elif event.name == "agent_cancelled":
            self._on_finished("")
            line = i18n.t("chat.cancelled")
            self.bubble.append_message("assistant", line)
            self._history.append(self._sid, "assistant", line)
        elif event.name == "confirmation_requested":
            self.signals.activity.emit(
                f"▸ {i18n.t('confirmation.pending')}: {event.payload.get('tool_name', '?')}"
            )
            from ui.confirmation import ask_confirmation

            approved = ask_confirmation(
                None,
                event.payload.get("tool_name", "?"),
                event.payload.get("question", ""),
                event.payload.get("arguments") or {},
            )
            self.runtime.resolve_confirmation(
                event.task_id, event.payload.get("confirm_id", ""), approved
            )
            self.signals.activity.emit("")

    def context_menu(self) -> QMenu:
        menu = QMenu()
        act_settings = QAction(i18n.t("menu.settings"), menu)
        act_settings.triggered.connect(self._open_settings)
        act_chat = QAction(i18n.t("menu.chat"), menu)
        act_chat.triggered.connect(self.bubble.toggle)
        char_menu = QMenu(i18n.t("menu.avatar"), menu)
        for name in self._avatar_names():
            act = QAction(name, char_menu)
            act.triggered.connect(lambda checked=False, n=name: self._switch_avatar(n))
            char_menu.addAction(act)
        act_switch_gui = QAction(i18n.t("menu.switch_gui"), menu)
        act_switch_gui.triggered.connect(self._switch_to_gui)
        act_quit = QAction(i18n.t("menu.quit"), menu)
        act_quit.triggered.connect(self.quit)
        menu.addAction(act_settings)
        menu.addAction(act_chat)
        menu.addMenu(char_menu)
        menu.addAction(act_switch_gui)
        menu.addSeparator()
        menu.addAction(act_quit)
        return menu

    def _switch_to_gui(self) -> None:
        restart_into(ui_json_path(), "gui")

    def _open_settings(self) -> None:
        self.settings_win.load()
        self.settings_win.show()
        self.settings_win.raise_()

    def _avatar_names(self) -> list[str]:
        return sorted(p.name for p in ASSETS.iterdir() if p.is_dir())

    def _switch_avatar(self, name: str) -> None:
        settings = load_settings(self.settings_path)
        settings["avatar"] = name
        self.settings_path.write_text(json.dumps(settings, indent=2))
        self.bubble.append_message("tool", i18n.t("chat.avatar_selected", name=name))

    def quit(self) -> None:
        self.runtime.close()
        QApplication.quit()

    def close(self) -> None:
        self.runtime.close()


def build_ui() -> App:
    from core.paths import ensure_user_config

    ensure_user_config()
    app = QApplication.instance() or QApplication(sys.argv)
    prefs = load_prefs(ui_json_path())
    i18n.set_language(prefs.lang)
    apply_theme(app, prefs.theme)
    try:
        ui = App()
    except Exception as exc:
        QMessageBox.critical(
            None,
            i18n.t("app.title"),
            f"Agent başlatılamadı:\n{exc}\n\nAyarları config/ altından kontrol edin.",
        )
        raise SystemExit(1) from exc
    app.aboutToQuit.connect(ui.runtime.close)
    app.aboutToQuit.connect(ui._history.close)
    return ui


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    ui = build_ui()
    ui.bubble.show()
    code = app.exec()
    os._exit(code)  # skip non-daemon ThreadPoolExecutor join on quit-while-busy


if __name__ == "__main__":
    sys.exit(main())

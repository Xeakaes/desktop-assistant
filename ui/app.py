"""M1 desktop entry: avatar + bubble + settings wired to the M0 agent runtime."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu

from core.bootstrap import DEFAULT_SECRETS, DEFAULT_SETTINGS, build_runtime
from core.config import load_settings
from ui.avatar.state_machine import reduce_event
from ui.avatar.window import AvatarWindow
from ui.bridge import QtBridge
from ui.bubble import BubbleWindow
from ui.settings import SettingsWindow

SID = "m1"
ASSETS = Path(__file__).resolve().parent.parent / "assets" / "avatars"


class _UiSignals(QObject):
    finished = Signal(str)
    activity = Signal(str)


class App:
    def __init__(self) -> None:
        self.settings_path = DEFAULT_SETTINGS
        self.secrets_path = DEFAULT_SECRETS
        self.runtime, self.bus, self.session = build_runtime()
        self._settings_cache = load_settings(self.settings_path)
        avatar_name = self._settings_cache.get("avatar", "base")
        self.avatar = AvatarWindow(
            ASSETS / avatar_name, context_menu_factory=self.context_menu
        )
        self.bubble = BubbleWindow(on_send=self._on_send, on_cancel=self._on_cancel)
        self.settings_win = SettingsWindow(self.settings_path, self.secrets_path)
        self.bridge = QtBridge(self.bus)
        self.signals = _UiSignals()
        self.signals.finished.connect(self._on_finished)
        self.signals.activity.connect(self.bubble.set_tool_activity)
        self.bridge.sig.connect(self._on_event)
        screen = QApplication.primaryScreen().geometry()
        self.avatar.move(screen.width() - 220, screen.height() - 260)
        self.avatar.show()
        self.bubble.move(max(0, self.avatar.x() - 340), max(0, self.avatar.y() - 80))

    def _on_send(self, text: str) -> None:
        self.bubble.append_message("user", text)
        self.bubble.set_busy(True)
        threading.Thread(target=self._run_agent, args=(text,), daemon=True).start()

    def _run_agent(self, text: str) -> None:
        try:
            tid = self.runtime.begin_task(SID, text)
            self.runtime.run_task(tid)
            final = ""
            for m in reversed(self.session.messages(SID)):
                if m.role == "assistant" and m.content:
                    final = m.content
                    break
            self.signals.finished.emit(final)
        except Exception as exc:
            self.signals.finished.emit(f"Hata: {exc}")

    def _on_finished(self, final: str) -> None:
        self.bubble.set_busy(False)
        self.bubble.set_tool_activity("")
        if final:
            self.bubble.append_message("assistant", final)

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
            self.signals.activity.emit(f"▸ {name} çalışıyor…")
            self.bubble.append_message("tool", f"{name} başladı")
        elif event.name == "tool_finished":
            name = event.payload.get("tool_name", "")
            ok = event.payload.get("ok", "")
            self.bubble.append_message("tool", f"{name} bitti ({ok})")
        elif event.name == "confirmation_requested":
            self.signals.activity.emit(
                f"▸ onay bekleniyor: {event.payload.get('tool_name', '?')}"
            )

    def context_menu(self) -> QMenu:
        menu = QMenu()
        act_settings = QAction("Ayarlar…", menu)
        act_settings.triggered.connect(self._open_settings)
        act_chat = QAction("Sohbet", menu)
        act_chat.triggered.connect(self.bubble.toggle)
        char_menu = QMenu("Karakter", menu)
        for name in self._avatar_names():
            act = QAction(name, char_menu)
            act.triggered.connect(lambda checked=False, n=name: self._switch_avatar(n))
            char_menu.addAction(act)
        act_quit = QAction("Çıkış", menu)
        act_quit.triggered.connect(self.quit)
        menu.addAction(act_settings)
        menu.addAction(act_chat)
        menu.addMenu(char_menu)
        menu.addSeparator()
        menu.addAction(act_quit)
        return menu

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
        self.bubble.append_message("tool", f"Avatar '{name}' seçildi — yeniden başlatın")

    def quit(self) -> None:
        self.runtime.close()
        QApplication.quit()

    def close(self) -> None:
        self.runtime.close()


def build_ui() -> App:
    app = QApplication.instance() or QApplication(sys.argv)
    ui = App()
    app.aboutToQuit.connect(ui.runtime.close)
    return ui


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    ui = build_ui()
    ui.bubble.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

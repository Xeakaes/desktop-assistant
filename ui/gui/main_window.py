"""GUI main window: sidebar, chat transcript, history browser (spec §4, §5)."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.history import HistoryStore
from ui.i18n import i18n
from ui.prefs import UiPrefs, load_prefs, save_prefs


class _Input(QPlainTextEdit):
    returnPressed = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
            == Qt.KeyboardModifier.NoModifier
        ):
            self.returnPressed.emit()
            return
        super().keyPressEvent(event)


class ChatWindow(QMainWindow):
    def __init__(self, runtime=None, history: HistoryStore | None = None,
                 ui_json_path: Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("main")
        self.resize(880, 600)
        self._runtime = runtime
        self._history = history or HistoryStore(Path("/tmp/desktop-assistant-test.db"))
        self._ui_json_path = ui_json_path or Path.home() / ".config" / "desktop-assistant" / "ui.json"
        self._session_id: str | None = None
        self._messages: list[dict] = []
        self._busy = False

        # --- sidebar ---
        self._new_chat_btn = QPushButton(self)
        self._new_chat_btn.clicked.connect(self.new_chat)
        self._sessions = QListWidget(self)
        self._sessions.itemClicked.connect(self._on_session_click)
        self._theme_btn = QPushButton(self)
        self._theme_btn.clicked.connect(self._toggle_theme)
        self._settings_btn = QPushButton(self)
        self._settings_btn.clicked.connect(self._open_settings)
        self._switch_avatar_btn = QPushButton(self)
        self._switch_avatar_btn.clicked.connect(self._switch_to_avatar)
        self._collapse_btn = QPushButton(self)
        self._collapse_btn.clicked.connect(self._toggle_sidebar)

        side_layout = QVBoxLayout()
        side_layout.addWidget(self._new_chat_btn)
        side_layout.addWidget(self._sessions, 1)
        side_layout.addWidget(self._theme_btn)
        side_layout.addWidget(self._settings_btn)
        side_layout.addWidget(self._switch_avatar_btn)
        side_layout.addWidget(self._collapse_btn)
        self._side_inner = QFrame(self)
        self._side_inner.setObjectName("sidebar")
        self._side_inner.setLayout(side_layout)
        self._side_inner.setFixedWidth(260)

        # --- chat ---
        self._msg_area = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_area)
        self._msg_layout.addStretch(1)
        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("chat")
        self._scroll.setWidget(self._msg_area)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._activity = QLabel("", self)
        self._activity.setObjectName("muted")
        self._chat_input = _Input(self)
        self._chat_input.setObjectName("chat_input")
        self._chat_input.setFixedHeight(80)
        self._chat_input.returnPressed.connect(self._send)
        self._send_btn = QPushButton(self)
        self._send_btn.clicked.connect(self._send)
        self._cancel_btn = QPushButton(self)
        self._cancel_btn.setObjectName("danger")
        self._cancel_btn.clicked.connect(self._cancel)

        bottom = QHBoxLayout()
        bottom.addWidget(self._chat_input, 1)
        bottom.addWidget(self._send_btn)
        bottom.addWidget(self._cancel_btn)

        right = QVBoxLayout()
        right.addWidget(self._scroll, 1)
        right.addWidget(self._activity)
        right.addLayout(bottom)
        right_w = QWidget(self)
        right_w.setLayout(right)

        central = QWidget(self)
        central_l = QHBoxLayout(central)
        central_l.setContentsMargins(0, 0, 0, 0)
        central_l.setSpacing(0)
        central_l.addWidget(self._side_inner)
        central_l.addWidget(right_w, 1)
        self.setCentralWidget(central)

        self.retranslate()
        self.new_chat()

    # --- i18n / theme ---

    def retranslate(self) -> None:
        t = i18n.t
        self.setWindowTitle(t("app.title"))
        self._new_chat_btn.setText(t("sidebar.new_chat"))
        self._theme_btn.setText(t("sidebar.theme"))
        self._settings_btn.setText(t("sidebar.settings"))
        self._switch_avatar_btn.setText(t("sidebar.switch_avatar"))
        self._collapse_btn.setText(t("sidebar.collapse"))
        self._chat_input.setPlaceholderText(t("chat.input_placeholder"))
        self._send_btn.setText(t("chat.send"))
        self._cancel_btn.setText(t("chat.cancel"))

    def _toggle_theme(self) -> None:
        prefs = load_prefs(self._ui_json_path)
        new = "light" if prefs.theme == "dark" else "dark"
        save_prefs(self._ui_json_path, UiPrefs(mode=prefs.mode, theme=new, lang=prefs.lang))
        app = self.window().windowHandle() and self.window().window().window()
        from PySide6.QtWidgets import QApplication

        from ui.theme import qss

        (app or QApplication.instance()).setStyleSheet(qss(new))

    def _toggle_sidebar(self) -> None:
        if self._side_inner.width() > 100:
            self._side_inner.setFixedWidth(48)
            self._new_chat_btn.hide()
            self._sessions.hide()
            self._theme_btn.hide()
            self._settings_btn.hide()
            self._switch_avatar_btn.hide()
            self._collapse_btn.setText(t_safe("sidebar.expand"))
        else:
            self._side_inner.setFixedWidth(260)
            for w in (
                self._new_chat_btn,
                self._sessions,
                self._theme_btn,
                self._settings_btn,
                self._switch_avatar_btn,
            ):
                w.show()
            self._collapse_btn.setText(t_safe("sidebar.collapse"))

    def _switch_to_avatar(self) -> None:
        prefs = load_prefs(self._ui_json_path)
        save_prefs(self._ui_json_path, UiPrefs(mode="avatar", theme=prefs.theme, lang=prefs.lang))
        self._restart()

    def _restart(self) -> None:
        import os
        import sys

        os.execv(sys.executable, [sys.executable, *sys.argv])

    def _open_settings(self) -> None:
        from ui.settings import SettingsWindow

        if getattr(self, "_settings_win", None) is None:
            self._settings_win = SettingsWindow(
                Path.home() / ".config" / "desktop-assistant" / "settings.json",
                Path.home() / ".config" / "desktop-assistant" / "secrets.json",
                self._ui_json_path,
            )
        self._settings_win.load()
        self._settings_win.show()
        self._settings_win.raise_()

    # --- sessions ---

    def new_chat(self) -> None:
        self._session_id = self._history.create_session()
        self._clear_messages()
        self._reload_sessions()
        self._chat_input.setFocus()

    def _clear_messages(self) -> None:
        for m in self._messages:
            if m.get("widget") is not None:
                m["widget"].setParent(None)
                m["widget"].deleteLater()
        self._messages.clear()

    def _reload_sessions(self) -> None:
        self._sessions.clear()
        for sid, title, _ts in self._history.list_sessions():
            item = QListWidgetItem(title or sid[:8])
            item.setData(Qt.ItemDataRole.UserRole, sid)
            self._sessions.addItem(item)

    def _on_session_click(self, item: QListWidgetItem) -> None:
        sid = item.data(Qt.ItemDataRole.UserRole)
        self._load_session(sid)

    def _load_session(self, session_id: str, force: bool = False) -> None:
        if not force and session_id == self._session_id:
            return
        self._session_id = session_id
        self._clear_messages()
        for role, content, tool_name in self._history.messages(session_id):
            self._append(role, content, tool_name=tool_name)

    # --- chat ---

    def _append(self, role: str, text: str, tool_name: str | None = None) -> dict:
        name = {"user": "msg_user", "assistant": "msg_assistant", "tool": "msg_tool"}.get(
            role, "msg_assistant"
        )
        frame = QFrame(self)
        frame.setObjectName(name)
        lbl = QLabel(text, frame)
        lbl.setWordWrap(True)
        lay = QHBoxLayout(frame)
        lay.addWidget(lbl)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, frame)
        frame.show()
        entry = {"role": role, "text": text, "objectName": name, "widget": frame}
        self._messages.append(entry)
        return entry

    def _send(self) -> None:
        if self._busy:
            return
        text = self._chat_input.toPlainText().strip()
        if not text or self._runtime is None and getattr(self, "_core", None) is None:
            if not text:
                return
        self._chat_input.clear()
        self._append("user", text)
        self._history.append(self._session_id, "user", text)
        self._set_busy(True)
        if getattr(self, "_core", None) is not None:
            self._run_core(self._core, text)
        else:
            threading.Thread(target=self._run_agent, args=(text,), daemon=True).start()

    def _run_core(self, core, text: str) -> None:
        try:
            for event in core.ask(text):
                name = event.get("event", "")
                if name == "token":
                    pass
                elif name == "assistant_message":
                    msg = event.get("text", "")
                    if msg:
                        self._append("assistant", msg)
                        self._history.append(self._session_id, "assistant", msg)
        finally:
            self._set_busy(False)

    def _run_agent(self, text: str) -> None:
        try:
            tid = self._runtime.begin_task(self._session_id, text)
            self._runtime.run_task(tid)
        except Exception as exc:
            self._append("assistant", f"{i18n.t('chat.error_prefix')}{exc}")
        finally:
            self._set_busy(False)

    def _cancel(self) -> None:
        if self._runtime is not None:
            self._runtime.cancel_active_task()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._send_btn.setEnabled(not busy)
        self._cancel_btn.setEnabled(busy)
        self._activity.setText(i18n.t("chat.activity_running") if busy else "")


def t_safe(key: str) -> str:
    try:
        return i18n.t(key)
    except Exception:
        return key

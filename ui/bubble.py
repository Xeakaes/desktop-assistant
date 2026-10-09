"""Chat bubble: transcript, input, tool activity line, cancel (spec §4.2, M2 prompts later)."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.i18n import i18n


class BubbleWindow(QFrame):
    def __init__(
        self,
        on_send: Callable[[str], None],
        on_cancel: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("bubble")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setMinimumSize(320, 220)

        self._on_send = on_send
        self._on_cancel = on_cancel

        self._transcript = QPlainTextEdit(self)
        self._transcript.setReadOnly(True)
        font = QFont("Sans Serif", 10)
        self._transcript.setFont(font)

        self._activity = QLabel("", self)
        self._activity.setWordWrap(True)

        self._input = QLineEdit(self)
        self._input.returnPressed.connect(self._send)

        self._send_btn = QPushButton(self)
        self._send_btn.clicked.connect(self._send)
        self._cancel_btn = QPushButton(self)
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._cancel_btn.setVisible(False)

        row = QHBoxLayout()
        row.addWidget(self._input, 1)
        row.addWidget(self._send_btn)
        row.addWidget(self._cancel_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self._transcript, 1)
        layout.addWidget(self._activity)
        layout.addLayout(row)

        from ui.i18n import language_bridge

        language_bridge.changed.connect(self.retranslate)
        self.retranslate()
        self.set_busy(False)

    def retranslate(self) -> None:
        self._input.setPlaceholderText(i18n.t("chat.input_placeholder"))
        self._send_btn.setText(i18n.t("chat.send"))
        self._cancel_btn.setText(i18n.t("chat.cancel"))

    def append_message(self, role: str, text: str) -> None:
        prefix = {
            "user": i18n.t("chat.user_prefix") + ":",
            "assistant": i18n.t("chat.assistant_prefix") + ":",
            "tool": "▸",
        }.get(role, role)
        self._transcript.appendPlainText(f"{prefix} {text}")

    def set_busy(self, busy: bool) -> None:
        self._input.setEnabled(not busy)
        self._send_btn.setEnabled(not busy)
        self._cancel_btn.setVisible(busy)
        self._cancel_btn.setEnabled(busy)

    def set_tool_activity(self, text: str) -> None:
        self._activity.setText(text)

    def toggle(self) -> None:
        self.setVisible(not self.isVisible())

    def _send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._on_send(text)

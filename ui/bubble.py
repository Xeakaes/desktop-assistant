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

_STYLE = """
#bubble {
    background: rgba(20, 24, 32, 220);
    border: 1px solid rgba(120, 200, 220, 90);
    border-radius: 12px;
}
#bubble QLabel { color: #9fd8e8; background: transparent; }
#bubble QPlainTextEdit { color: #e8eef2; background: transparent; border: none; }
#bubble QLineEdit { color: #e8eef2; background: rgba(255,255,255,20);
    border: 1px solid rgba(120,200,220,80); border-radius: 6px; padding: 4px 8px; }
#bubble QPushButton { color: #e8eef2; background: rgba(120,200,220,60);
    border: none; border-radius: 6px; padding: 4px 12px; }
#bubble QPushButton:hover { background: rgba(120,200,220,100); }
"""


class BubbleWindow(QFrame):
    def __init__(
        self,
        on_send: Callable[[str], None],
        on_cancel: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("bubble")
        self.setStyleSheet(_STYLE)
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
        self._input.setPlaceholderText("Mesaj yazın…")
        self._input.returnPressed.connect(self._send)

        self._send_btn = QPushButton("Gönder", self)
        self._send_btn.clicked.connect(self._send)
        self._cancel_btn = QPushButton("İptal", self)
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

        self.set_busy(False)

    def append_message(self, role: str, text: str) -> None:
        prefix = {"user": "Sen:", "assistant": "Asistan:", "tool": "▸"}.get(role, role)
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

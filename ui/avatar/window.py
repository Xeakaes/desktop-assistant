"""Frameless transparent avatar window driven by manifest animations (spec §4.1)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.avatar.manifest import StateAnim, load_manifest
from ui.avatar.state_machine import AvatarState

DISPLAY_H = 160


def error_timeout_ms() -> int:
    return 3000


class AvatarWindow(QWidget):
    def __init__(self, avatar_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._states: dict[str, StateAnim] = load_manifest(avatar_dir / "manifest.json")
        self._state: AvatarState = "idle"
        self._frame_index = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._label = QLabel(self)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.timeout.connect(lambda: self.set_state("idle"))

        self._render_frame()
        self._start_timer()

    def current_state(self) -> AvatarState:
        return self._state

    def set_state(self, state: AvatarState) -> None:
        if state == self._state and state != "error":
            return
        self._state = state
        self._frame_index = 0
        self._start_timer()
        self._render_frame()
        if state == "error":
            self._error_timer.start(error_timeout_ms())
        else:
            self._error_timer.stop()

    def _start_timer(self) -> None:
        anim = self._states[self._state]
        interval = max(1, int(1000 / anim.fps))
        self._timer.setInterval(interval)
        self._timer.start()

    def _advance(self) -> None:
        anim = self._states[self._state]
        if self._frame_index >= len(anim.frames) - 1:
            if anim.loop:
                self._frame_index = 0
            else:
                self._timer.stop()
                return
        else:
            self._frame_index += 1
        self._render_frame()

    def _render_frame(self) -> None:
        anim = self._states[self._state]
        path = anim.frames[self._frame_index]
        pix = QPixmap(path)
        if pix.isNull():
            self._label.setText("[!]")
            return
        scaled = pix.scaledToHeight(
            DISPLAY_H, Qt.TransformationMode.FastTransformation
        )
        self._label.setPixmap(scaled)
        self.resize(scaled.width(), scaled.height())

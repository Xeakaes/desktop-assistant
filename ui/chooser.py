"""First-run mode chooser dialog (spec §6)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ui.i18n import i18n


class ModeChooser(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.t("mode.choose_title"))
        self.setMinimumWidth(320)
        self.chosen: str | None = None

        body = QLabel(i18n.t("mode.choose_body"), self)
        body.setWordWrap(True)

        gui_btn = QPushButton(i18n.t("mode.gui"), self)
        gui_btn.clicked.connect(lambda: self._pick("gui"))
        avatar_btn = QPushButton(i18n.t("mode.avatar"), self)
        avatar_btn.clicked.connect(lambda: self._pick("avatar"))

        row = QHBoxLayout()
        row.addWidget(gui_btn)
        row.addWidget(avatar_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(body)
        layout.addLayout(row)

    def _pick(self, mode: str) -> None:
        self.chosen = mode
        self.accept()

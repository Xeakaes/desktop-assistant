"""Bundled UI font loading (spec section 4.2)."""
from __future__ import annotations

from pathlib import Path

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
REGULAR_PATH = _FONT_DIR / "Nunito-Regular.ttf"
BOLD_PATH = _FONT_DIR / "Nunito-Bold.ttf"


def load_fonts(app) -> int:
    """Load bundled Nunito Regular+Bold, set app font; id or -1 (never raises)."""
    if not REGULAR_PATH.is_file():
        return -1
    try:
        from PySide6.QtGui import QFont, QFontDatabase

        font_id = QFontDatabase.addApplicationFont(str(REGULAR_PATH))
        if font_id == -1:
            return -1
        if BOLD_PATH.is_file():
            QFontDatabase.addApplicationFont(str(BOLD_PATH))
        app.setFont(QFont("Nunito"))
        return font_id
    except Exception:
        return -1

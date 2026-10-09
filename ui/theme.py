"""Dark/light theme token palettes and QSS builder (spec §6)."""

from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#12161c",
        "bg_alt": "#1a2028",
        "fg": "#e8eef2",
        "fg_muted": "#8a97a3",
        "accent": "#2fb6c4",
        "accent_hover": "#45cdd9",
        "border": "#2a3440",
        "bubble_user": "#243848",
        "bubble_assistant": "#1e2830",
        "danger": "#e05c5c",
    },
    "light": {
        "bg": "#f4f6f8",
        "bg_alt": "#e8edf1",
        "fg": "#1a222a",
        "fg_muted": "#5a6874",
        "accent": "#0e8a96",
        "accent_hover": "#0c7480",
        "border": "#c8d2da",
        "bubble_user": "#d4e8f0",
        "bubble_assistant": "#eef2f5",
        "danger": "#c0392b",
    },
}

REQUIRED_OBJECTNAMES: tuple[str, ...] = (
    "main",
    "sidebar",
    "chat",
    "chat_input",
    "msg_user",
    "msg_assistant",
    "msg_tool",
    "bubble",
    "settings_win",
)


def qss(theme_name: str) -> str:
    if theme_name not in THEMES:
        raise ValueError(f"unknown theme: {theme_name}")
    t = THEMES[theme_name]
    return f"""
QWidget#main {{ background: {t['bg']}; color: {t['fg']}; }}
QFrame#sidebar {{ background: {t['bg_alt']}; border-right: 1px solid {t['border']}; }}
QFrame#sidebar QPushButton {{ background: transparent; color: {t['fg']};
    border: 1px solid {t['border']}; border-radius: 6px; padding: 6px 10px; }}
QFrame#sidebar QPushButton:hover {{ background: {t['accent']}; color: {t['bg']}; }}
QListWidget {{ background: {t['bg']}; color: {t['fg']};
    border: 1px solid {t['border']}; border-radius: 6px; }}
QListWidget::item:selected {{ background: {t['accent']}; color: {t['bg']}; }}
QScrollArea#chat {{ background: {t['bg']}; border: none; }}
QFrame#msg_user {{ background: {t['bubble_user']}; border-radius: 10px; }}
QFrame#msg_assistant {{ background: {t['bubble_assistant']}; border-radius: 10px; }}
QFrame#msg_tool {{ background: {t['bg_alt']}; border-radius: 8px; }}
QPlainTextEdit#chat_input, QLineEdit {{ background: {t['bg_alt']}; color: {t['fg']};
    border: 1px solid {t['border']}; border-radius: 8px; padding: 6px 10px; }}
QLabel {{ color: {t['fg']}; background: transparent; }}
QLabel#muted {{ color: {t['fg_muted']}; }}
QPushButton {{ background: {t['accent']}; color: {t['bg']};
    border: none; border-radius: 8px; padding: 8px 16px; }}
QPushButton:hover {{ background: {t['accent_hover']}; }}
QPushButton:disabled {{ background: {t['border']}; color: {t['fg_muted']}; }}
QPushButton#danger {{ background: {t['danger']}; }}
QFrame#bubble {{ background: {t['bg_alt']}; border: 1px solid {t['border']};
    border-radius: 12px; }}
QFrame#bubble QPlainTextEdit, QFrame#bubble QLineEdit {{ background: {t['bg']};
    color: {t['fg']}; border: 1px solid {t['border']}; border-radius: 6px; }}
QFrame#bubble QPushButton {{ background: {t['accent']}; color: {t['bg']}; }}
QWidget#settings_win {{ background: {t['bg']}; color: {t['fg']}; }}
QComboBox {{ background: {t['bg_alt']}; color: {t['fg']};
    border: 1px solid {t['border']}; border-radius: 6px; padding: 4px 8px; }}
QMenu {{ background: {t['bg_alt']}; color: {t['fg']};
    border: 1px solid {t['border']}; }}
QMenu::item:selected {{ background: {t['accent']}; color: {t['bg']}; }}
"""


def apply_theme(app, theme_name: str) -> None:
    app.setStyleSheet(qss(theme_name))

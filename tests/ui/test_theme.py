import pytest

from ui.theme import REQUIRED_OBJECTNAMES, THEMES, qss


def test_qss_unknown_raises():
    with pytest.raises(ValueError):
        qss("neon")


def test_qss_covers_required_objectnames():
    for name in ("dark", "light"):
        out = qss(name)
        for on in REQUIRED_OBJECTNAMES:
            assert f"#{on}" in out, (name, on)


def test_dark_and_light_differ():
    assert qss("dark") != qss("light")


def test_tokens_present():
    for name, tokens in THEMES.items():
        for key in (
            "bg", "bg_alt", "fg", "fg_muted", "accent",
            "accent_hover", "border", "bubble_user", "bubble_assistant", "danger",
        ):
            assert tokens.get(key), (name, key)


def test_themes_have_identical_token_keys():
    assert set(THEMES["dark"]) == set(THEMES["light"])
    expected = {
        "bg", "bg_alt", "surface", "surface_hover", "border", "input_border",
        "fg", "fg_muted", "accent", "accent_hover", "bubble_user",
        "bubble_assistant", "danger", "on_accent", "on_danger",
    }
    assert set(THEMES["dark"]) == expected


def _srgb_to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def contrast(hex_a: str, hex_b: str) -> float:
    """WCAG 2.1 contrast ratio between two #rrggbb colors."""
    def lum(h: str) -> float:
        r, g, b = (int(h[i : i + 2], 16) / 255 for i in (1, 3, 5))
        return 0.2126 * _srgb_to_lin(r) + 0.7152 * _srgb_to_lin(g) + 0.0722 * _srgb_to_lin(b)

    la, lb = lum(hex_a), lum(hex_b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_contrast_ratios_meet_thresholds():
    # Text pairs >= 4.5; UI-component pairs >= 3 (spec section 6).
    for name in ("dark", "light"):
        t = THEMES[name]
        assert contrast(t["fg"], t["bg"]) >= 4.5, (name, "fg/bg")
        assert contrast(t["on_accent"], t["accent"]) >= 4.5, (name, "on_accent/accent")
        assert contrast(t["on_danger"], t["danger"]) >= 4.5, (name, "on_danger/danger")
        assert contrast(t["fg_muted"], t["surface"]) >= 4.5, (name, "fg_muted/surface")
        assert contrast(t["input_border"], t["bg"]) >= 3.0, (name, "input_border/bg")
        assert contrast(t["input_border"], t["surface"]) >= 3.0, (name, "input_border/surface")


def test_focus_rules_per_selector():
    import re

    for name in ("dark", "light"):
        style = qss(name)
        # Filled buttons: focus swaps the reserved 2px border to fg so the
        # change is visible against the accent fill (accent->accent_hover
        # is ~1.2:1). Inputs/combos/outline swap to accent (>= 3:1 vs bg).
        m = re.search(r"(?:^|\n)QPushButton\s*\{[^}]*\}", style)
        assert m and "border: 2px" in m.group(0), name
        m = re.search(r"(?:^|\n)QPushButton:focus\s*\{[^}]*\}", style)
        assert m and THEMES[name]["fg"] in m.group(0), name
        for sel in ("QPlainTextEdit#chat_input, QLineEdit", "QComboBox"):
            m = re.search(rf"(?:^|\n){re.escape(sel)}\s*\{{[^}}]*\}}", style)
            assert m and "border: 2px" in m.group(0), (name, sel)


def test_qss_parses_without_qt_warnings():
    """Qt reports broken stylesheets only via the message handler; capture it."""
    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    captured: list[str] = []

    def _handler(mode, ctx, msg):
        captured.append(msg)

    prev = qInstallMessageHandler(_handler)
    try:
        for name in ("dark", "light"):
            app.setStyleSheet(qss(name))
            app.processEvents()
    finally:
        qInstallMessageHandler(prev)
        app.setStyleSheet("")
    parse_errors = [m for m in captured if "Could not parse stylesheet" in m]
    assert not parse_errors, parse_errors


def test_qss_has_scrollbar_tabs_and_outline():
    style = qss("dark")
    assert "QScrollBar" in style
    assert "QTabWidget" in style
    assert "QPushButton#outline" in style
    assert "QFrame#empty_state" in style
    assert "QLabel#sessions_header" in style
    assert "QPushButton#new_chat" in style

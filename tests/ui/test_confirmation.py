"""Confirmation dialog tests (P1). Regression: clickedButton AttributeError."""

from __future__ import annotations

from ui import confirmation
from ui.i18n import i18n


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _button(dlg, label):
    from PySide6.QtWidgets import QDialogButtonBox

    for box in dlg.findChildren(QDialogButtonBox):
        for b in box.buttons():
            if b.text() == label:
                return b
    raise AssertionError(f"button not found: {label}")


def test_allow_click_sets_choice():
    _app()
    dlg, choice = confirmation._build_dialog(None, "shell", "Run shell?", {"cmd": "ls"})
    assert choice["allow"] is False
    _button(dlg, i18n.t("confirmation.allow")).click()
    assert choice["allow"] is True
    dlg.close()


def test_deny_click_keeps_choice_false():
    _app()
    dlg, choice = confirmation._build_dialog(None, "shell", "Run shell?", {})
    _button(dlg, i18n.t("confirmation.deny")).click()
    assert choice["allow"] is False
    dlg.close()


def test_deny_is_styled_as_outline():
    """Deny must be the quiet outline button; Allow stays the single accent."""
    _app()
    dlg, _choice = confirmation._build_dialog(None, "shell", "?", {})
    deny = _button(dlg, i18n.t("confirmation.deny"))
    allow = _button(dlg, i18n.t("confirmation.allow"))
    assert deny.property("outline") is True
    assert not allow.property("outline")
    dlg.close()


def test_dialog_close_is_deny_by_default():
    """X/ESC (rejected) must leave choice False -> deny (safe default)."""
    _app()
    dlg, choice = confirmation._build_dialog(None, "screenshot", "?", None)
    assert choice["allow"] is False
    dlg.reject()
    assert choice["allow"] is False
    dlg.close()


def test_ask_confirmation_has_no_clicked_button_api():
    """Regression guard: QDialogButtonBox has no clickedButton()."""
    from PySide6.QtWidgets import QDialogButtonBox

    _app()
    assert not hasattr(QDialogButtonBox(), "clickedButton")

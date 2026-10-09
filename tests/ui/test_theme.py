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

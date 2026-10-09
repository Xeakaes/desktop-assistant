import json

import pytest

from ui.prefs import UiPrefs, load_prefs, save_prefs, switch_mode


def test_missing_file_defaults(tmp_path):
    p = tmp_path / "ui.json"
    prefs = load_prefs(p)
    assert prefs.mode is None
    assert prefs.theme == "dark"
    assert prefs.lang == "tr"


def test_load_ui_config_invalid_mode_returns_none(tmp_path):
    p = tmp_path / "ui.json"
    p.write_text(json.dumps({"mode": "web", "theme": "neon", "lang": "fr"}))
    prefs = load_prefs(p)
    assert prefs.mode is None
    assert prefs.theme == "dark"
    assert prefs.lang == "tr"


def test_bad_json_returns_defaults(tmp_path):
    p = tmp_path / "ui.json"
    p.write_text("{not json")
    prefs = load_prefs(p)
    assert prefs.mode is None and prefs.theme == "dark" and prefs.lang == "tr"


def test_roundtrip(tmp_path):
    p = tmp_path / "ui.json"
    save_prefs(p, UiPrefs(mode="gui", theme="light", lang="en"))
    prefs = load_prefs(p)
    assert prefs == UiPrefs(mode="gui", theme="light", lang="en")


def test_switch_mode_writes_file(tmp_path):
    p = tmp_path / "ui.json"
    switch_mode(p, "avatar")
    assert load_prefs(p).mode == "avatar"


def test_switch_mode_rejects_unknown(tmp_path):
    with pytest.raises(ValueError):
        switch_mode(tmp_path / "ui.json", "web")

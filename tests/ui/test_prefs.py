import json
import sys
import types

import pytest

from ui.prefs import (
    UiPrefs,
    load_prefs,
    restart_argv,
    save_prefs,
    switch_mode,
)


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


def test_restart_argv_keeps_dash_m(monkeypatch):
    """python -m pkg.mod must re-exec with -m, else sys.path[0] breaks."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "argv", ["/x/ui/app.py", "--foo"])
    fake_spec = types.SimpleNamespace(name="ui.app")
    main_mod = types.ModuleType("__main__")
    main_mod.__spec__ = fake_spec
    monkeypatch.setitem(sys.modules, "__main__", main_mod)
    argv = restart_argv()
    assert argv[1:3] == ["-m", "ui.app"]
    assert "--foo" in argv


def test_restart_argv_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/opt/app/desktop-assistant")
    monkeypatch.setattr(sys, "argv", ["/opt/app/desktop-assistant", "--flag"])
    argv = restart_argv()
    assert argv == ["/opt/app/desktop-assistant", "--flag"]


def test_restart_argv_plain_script(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "argv", ["/x/script.py"])
    main_mod = types.ModuleType("__main__")
    main_mod.__spec__ = None
    monkeypatch.setitem(sys.modules, "__main__", main_mod)
    argv = restart_argv()
    assert argv[1] == "/x/script.py"

import socket
import sys
from pathlib import Path

from app_entry import entry


def test_version_flag_prints(capsys):
    assert entry.main(["--version"]) == 0
    assert "0.0.0" in capsys.readouterr().out


def test_spawn_disabled_settings(monkeypatch):
    called = []
    monkeypatch.setattr(entry.subprocess, "Popen", lambda *a, **k: called.append(a))
    assert entry.maybe_spawn_server({"screen_control": {"enabled": False}}) is None
    assert called == []


def test_spawn_skipped_when_port_open(monkeypatch):
    class FakeSock:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(entry.socket, "create_connection", lambda *a, **k: FakeSock())
    assert entry.maybe_spawn_server({"screen_control": {"enabled": True}}) is None


def test_spawn_happens_when_port_closed(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise OSError("closed")

    monkeypatch.setattr(entry.socket, "create_connection", boom)
    captured = {}

    class P:
        pid = 4242

        def __init__(self, *a, **k):
            captured["args"] = a
            captured["kwargs"] = k

    monkeypatch.setattr(entry.subprocess, "Popen", P)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(
        __import__("core.paths", fromlist=["Path"]).Path,
        "home",
        classmethod(lambda cls: tmp_path),
    )
    pid = entry.maybe_spawn_server({"screen_control": {"enabled": True}})
    assert pid == "4242"
    assert "--serve-screen-control" in captured["args"][0]
    from core.paths import config_dir

    assert captured["kwargs"]["env"]["SCREEN_CONTROL_DATA_DIR"] == str(config_dir())


def test_serve_flag_dispatches(monkeypatch):
    seen = {}

    def fake_serve(argv):
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(entry, "serve_screen_control", fake_serve)
    assert entry.main(["--serve-screen-control"]) == 0
    assert "argv" in seen

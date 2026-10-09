"""Avatar app tests: P0 (real session, no FK error) + P1 (confirmation resolve)."""

from __future__ import annotations

import threading

import pytest


class FakeBus:
    def subscribe(self, *a, **k):
        pass

    def unsubscribe(self, *a, **k):
        pass


class FakeRuntime:
    def __init__(self):
        self.begin_calls: list[tuple[str, str]] = []
        self.resolve_calls: list[tuple[str, str, bool]] = []
        self._gate: threading.Event | None = None
        self._resume: threading.Event | None = None

    def begin_task(self, sid, text):
        self.begin_calls.append((sid, text))
        return "tid"

    def run_task(self, tid):
        pass

    def close(self):
        pass

    def resolve_confirmation(self, task_id, confirm_id, approved):
        self.resolve_calls.append((task_id, confirm_id, approved))


def _make_app(tmp_path, monkeypatch, runtime=None):
    from PySide6.QtWidgets import QApplication

    import ui.avatar_app as aa
    from ui.history import HistoryStore

    app = QApplication.instance() or QApplication([])
    rt = runtime or FakeRuntime()
    monkeypatch.setattr(aa, "build_runtime", lambda: (rt, FakeBus(), "sess"))
    monkeypatch.setattr(
        aa,
        "load_settings",
        lambda p: {"avatar": "base", "screen_control": {"enabled": False}},
    )
    monkeypatch.setattr(aa, "HistoryStore", lambda p: HistoryStore(tmp_path / "h.db"))
    monkeypatch.setattr(aa, "maybe_spawn_server", lambda s: None, raising=False)

    class FakeSettingsWin:
        def __init__(self, *a, **k):
            pass

        def load(self):
            pass

        def show(self):
            pass

        def raise_(self):
            pass

    monkeypatch.setattr(aa, "SettingsWindow", FakeSettingsWin)
    ui = aa.App()
    return app, ui, rt


def test_avatar_first_message_no_fk_error(tmp_path, monkeypatch):
    """P0: first user message must persist without FOREIGN KEY error."""
    app, ui, rt = _make_app(tmp_path, monkeypatch)
    sid = ui._sid
    assert sid, "avatar app must expose a real session id"
    sessions = [s[0] for s in ui._history.list_sessions()]
    assert sid in sessions, "session must exist in history store before messages"
    # must not raise sqlite3.IntegrityError (FK)
    ui._on_send("merhaba")
    msgs = ui._history.messages(sid)
    assert msgs and msgs[0] == ("user", "merhaba", None)
    ui.close()


def test_avatar_begin_task_uses_real_session(tmp_path, monkeypatch):
    app, ui, rt = _make_app(tmp_path, monkeypatch)
    ui._on_send("selam")
    assert rt.begin_calls, "agent thread must start"
    sid, text = rt.begin_calls[0]
    assert sid == ui._sid
    assert text == "selam"
    ui.close()


def test_avatar_confirmation_resolve_approved(tmp_path, monkeypatch):
    """P1 avatar: confirmation_requested must resolve via runtime."""
    from core.events import Event

    app, ui, rt = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "ui.confirmation.ask_confirmation", lambda *a, **k: True, raising=False
    )
    ev = Event(
        "confirmation_requested",
        ui._sid,
        "t1",
        {
            "confirm_id": "c9",
            "tool_name": "screenshot",
            "question": "Run tool screenshot?",
            "arguments": {},
        },
    )
    ui._on_event(ev)
    assert rt.resolve_calls == [("t1", "c9", True)]
    ui.close()


def test_avatar_confirmation_resolve_denied(tmp_path, monkeypatch):
    from core.events import Event

    app, ui, rt = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "ui.confirmation.ask_confirmation", lambda *a, **k: False, raising=False
    )
    ev = Event(
        "confirmation_requested",
        ui._sid,
        "t1",
        {"confirm_id": "c1", "tool_name": "shell", "question": "?", "arguments": {}},
    )
    ui._on_event(ev)
    assert rt.resolve_calls == [("t1", "c1", False)]
    ui.close()

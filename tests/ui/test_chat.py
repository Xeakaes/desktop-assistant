from pathlib import Path

from ui.history import HistoryStore


def _make_window(tmp_path):
    from PySide6.QtWidgets import QApplication

    from ui.gui.main_window import ChatWindow

    app = QApplication.instance() or QApplication([])
    db = tmp_path / "history.db"
    store = HistoryStore(db)
    win = ChatWindow(history=store)
    return app, win


class FakeRuntime:
    def __init__(self, win):
        self._win = win

    def begin_task(self, sid, text):
        from ui.gui.main_window import _UiSignals  # noqa: F401

        self._win._signals.assistant.emit("merhaba")
        self._win._signals.finished.emit()
        return "tid"

    def run_task(self, tid):
        pass

    def cancel_active_task(self):
        pass


def test_sends_and_appends(tmp_path):
    app, win = _make_window(tmp_path)
    win._runtime = FakeRuntime(win)
    win._chat_input.setPlainText("selam")
    win._send()
    assert win._messages[-1]["role"] == "user"
    assert win._messages[-1]["text"] == "selam"
    assert win._messages[-1]["objectName"] == "msg_user"
    # history row persisted
    msgs = win._history.messages(win._session_id)
    assert msgs[0] == ("user", "selam", None)
    win.hide()


def test_enter_sends_shift_enter_newline(tmp_path):
    app, win = _make_window(tmp_path)
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import Qt

    ev = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier
    )
    sent = []
    monkey = lambda *a: sent.append(True)
    win._send = monkey
    win._chat_input.keyPressEvent(ev)
    assert sent == [True]
    ev2 = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier,
    )
    win._chat_input.keyPressEvent(ev2)
    assert sent == [True]  # shift+enter did not send
    win.hide()


def test_history_click_loads_session(tmp_path):
    app, win = _make_window(tmp_path)
    sid = win._history.create_session("ilk sohbet")
    win._history.append(sid, "user", "eski mesaj")
    win._reload_sessions()
    win._load_session(sid, force=True)
    assert win._messages[0]["text"] == "eski mesaj"
    win.hide()


def test_sidebar_toggle_width(tmp_path):
    app, win = _make_window(tmp_path)
    assert win._side_inner.width() == 260
    win._toggle_sidebar()
    assert win._side_inner.width() == 48
    win._toggle_sidebar()
    assert win._side_inner.width() == 260
    win.hide()


def test_confirmation_requested_resolves_approved(tmp_path, monkeypatch):
    """P1 GUI: confirmation_requested must resolve via runtime with Allow."""
    from core.events import Event

    app, win = _make_window(tmp_path)
    resolved = []

    class RT:
        def resolve_confirmation(self, task_id, confirm_id, approved):
            resolved.append((task_id, confirm_id, approved))

    win._runtime = RT()
    monkeypatch.setattr("ui.confirmation.ask_confirmation", lambda *a, **k: True)
    ev = Event(
        "confirmation_requested",
        win._session_id,
        "t1",
        {
            "confirm_id": "c1",
            "tool_name": "shell",
            "question": "Run tool shell?",
            "arguments": {"cmd": "ls"},
        },
    )
    win._on_event(ev)
    assert resolved == [("t1", "c1", True)]
    win.hide()


def test_confirmation_requested_resolves_denied(tmp_path, monkeypatch):
    from core.events import Event

    app, win = _make_window(tmp_path)
    resolved = []

    class RT:
        def resolve_confirmation(self, task_id, confirm_id, approved):
            resolved.append((task_id, confirm_id, approved))

    win._runtime = RT()
    monkeypatch.setattr("ui.confirmation.ask_confirmation", lambda *a, **k: False)
    ev = Event(
        "confirmation_requested",
        win._session_id,
        "t1",
        {"confirm_id": "c7", "tool_name": "shell", "question": "?", "arguments": {}},
    )
    win._on_event(ev)
    assert resolved == [("t1", "c7", False)]
    win.hide()


def test_send_session_id_snapshotted_at_send_time(tmp_path, monkeypatch):
    """P2: switching chats mid-task must not rebind the running task."""
    import threading as _t

    app, win = _make_window(tmp_path)
    started = []

    class RT:
        def begin_task(self, sid, text):
            started.append(sid)
            return "tid"

        def run_task(self, tid):
            pass

        def cancel_active_task(self):
            pass

    win._runtime = RT()
    old_sid = win._session_id

    created = []

    class FakeThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self._target = target
            self._args = args
            created.append(self)

        def start(self):
            pass  # hold the worker until the test releases it

    monkeypatch.setattr(_t, "Thread", FakeThread)
    win._chat_input.setPlainText("selam")
    win._send()
    assert created, "worker thread must be created"
    win.new_chat()
    new_sid = win._session_id
    assert new_sid != old_sid
    created[0]._target(*created[0]._args)
    assert started == [old_sid], "task must bind to the session active at send time"
    win.hide()

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

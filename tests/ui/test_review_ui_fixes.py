"""Regression tests for review findings: chat area background,
Delete shortcut scope, session menu on empty area, agent_finished filter."""

from __future__ import annotations

from pathlib import Path

from ui.history import HistoryStore


def _make_window(tmp_path):
    from PySide6.QtWidgets import QApplication

    from ui.gui.main_window import ChatWindow

    app = QApplication.instance() or QApplication([])
    store = HistoryStore(tmp_path / "history.db")
    win = ChatWindow(history=store)
    return app, win


def test_msg_area_objectname_and_stylesheet(tmp_path):
    from ui.theme import qss

    app, win = _make_window(tmp_path)
    assert win._msg_area.objectName() == "msg_area"
    for theme in ("dark", "light"):
        assert "QWidget#msg_area" in qss(theme)
    win.hide()


def test_delete_shortcut_is_widget_scoped(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QShortcut

    app, win = _make_window(tmp_path)
    shortcuts = [
        s for s in win.findChildren(QShortcut)
        if s.key() == __import__("PySide6.QtGui", fromlist=["QKeySequence"]).QKeySequence(Qt.Key.Key_Delete)
    ]
    assert shortcuts, "expected a Delete shortcut on the sessions list"
    for s in shortcuts:
        assert s.context() == Qt.ShortcutContext.WidgetShortcut
    win.hide()


def test_session_menu_empty_area_shows_no_menu(tmp_path, monkeypatch):
    app, win = _make_window(tmp_path)
    sid = win._history.create_session("a")
    win._reload_sessions()
    win._sessions.setCurrentRow(0)

    shown = []

    class FakeMenu:
        def __init__(self, *a, **k):
            pass

        def addAction(self, *a, **k):
            return object()

        def exec(self, *a, **k):
            shown.append(True)
            return None

    import ui.gui.main_window as mw

    monkeypatch.setattr(mw, "QMenu", FakeMenu)
    # Right-click far below any item: itemAt() returns None.
    from PySide6.QtCore import QPoint

    win._on_session_menu(QPoint(5, win._sessions.height() + 50))
    assert shown == []
    win.hide()


def test_agent_finished_filtered_by_session(tmp_path):
    from core.events import Event

    app, win = _make_window(tmp_path)
    win._session_id = "s1"
    win._set_busy(True)
    finished = []
    win._signals.finished.connect(lambda: finished.append(True))

    win._on_event(Event("agent_finished", "other-session", "t1", {}))
    assert finished == []
    assert win._busy is True

    win._on_event(Event("agent_finished", "s1", "t1", {}))
    assert finished == [True]
    win.hide()

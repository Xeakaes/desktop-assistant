import threading
from pathlib import Path

from ui.history import HistoryStore


def test_create_list_append_messages(tmp_path):
    h = HistoryStore(tmp_path / "h.db")
    sid = h.create_session()
    h.append(sid, "user", "merhaba dünya bu ilk mesaj")
    h.append(sid, "assistant", "selam")
    h.append(sid, "tool", "ok", tool_name="screenshot")
    sessions = h.list_sessions()
    assert len(sessions) == 1
    assert sessions[0][1].startswith("merhaba")
    msgs = h.messages(sid)
    assert msgs[0] == ("user", "merhaba dünya bu ilk mesaj", None)
    assert msgs[2] == ("tool", "ok", "screenshot")
    h.close()


def test_auto_title_truncated_40(tmp_path):
    h = HistoryStore(tmp_path / "h.db")
    sid = h.create_session()
    h.append(sid, "user", "x" * 100)
    title = h.list_sessions()[0][1]
    assert len(title) == 40
    h.close()


def test_rename_and_delete_cascade(tmp_path):
    h = HistoryStore(tmp_path / "h.db")
    sid = h.create_session("old")
    h.append(sid, "user", "hi")
    h.rename_session(sid, "yeni başlık")
    assert h.list_sessions()[0][1] == "yeni başlık"
    h.delete_session(sid)
    assert h.list_sessions() == []
    assert h.messages(sid) == []
    h.close()


def test_sessions_newest_first(tmp_path):
    h = HistoryStore(tmp_path / "h.db")
    a = h.create_session("a")
    b = h.create_session("b")
    ids = [s[0] for s in h.list_sessions()]
    assert ids[0] == b
    h.close()


def test_append_from_multiple_threads_roundtrips(tmp_path):
    h = HistoryStore(tmp_path / "h.db")
    sid = h.create_session("t")

    def worker():
        for i in range(50):
            h.append(sid, "tool", f"m{i}")

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(h.messages(sid)) == 100
    h.close()


def test_reopen_same_path(tmp_path):
    p = tmp_path / "h.db"
    h1 = HistoryStore(p)
    sid = h1.create_session("keep")
    h1.close()
    h2 = HistoryStore(p)
    assert h2.list_sessions()[0][1] == "keep"
    h2.close()


def test_default_db_path_is_under_home():
    p = HistoryStore.__module__  # module loads
    from ui.history import default_db_path

    path = default_db_path()
    assert path.name == "history.db"
    assert "desktop-assistant" in str(path)

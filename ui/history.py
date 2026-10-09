"""SQLite chat-history store (spec §5). Pure Python, no Qt."""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from pathlib import Path

from core.paths import data_dir


def default_db_path() -> Path:
    return data_dir() / "history.db"


class HistoryStore:
    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_name TEXT,
                    ts REAL NOT NULL
                )
                """
            )

    def create_session(self, title: str = "") -> str:
        sid = uuid.uuid4().hex
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
                (sid, title, time.time()),
            )
        return sid

    def rename_session(self, session_id: str, title: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE sessions SET title = ? WHERE id = ?", (title, session_id)
            )

    def list_sessions(self) -> list[tuple[str, str, float]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, title, created_at FROM sessions ORDER BY created_at DESC"
            ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    def append(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: str | None = None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO messages (session_id, role, content, tool_name, ts)"
                " VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, tool_name, time.time()),
            )
            if role == "user":
                row = self._conn.execute(
                    "SELECT title FROM sessions WHERE id = ?", (session_id,)
                ).fetchone()
                if row is not None and not row[0]:
                    self._conn.execute(
                        "UPDATE sessions SET title = ? WHERE id = ?",
                        (content[:40], session_id),
                    )

    def messages(self, session_id: str) -> list[tuple[str, str, str | None]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content, tool_name FROM messages"
                " WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    def delete_session(self, session_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def close(self) -> None:
        with self._lock:
            self._conn.close()

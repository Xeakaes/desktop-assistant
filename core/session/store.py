"""In-memory session/message store (spec §3.6; SQLite later behind same API)."""

from __future__ import annotations

import uuid

from core.providers.base import ChatMessage, ToolCall


class SessionStore:
    def __init__(self) -> None:
        self._messages: dict[str, list[ChatMessage]] = {}

    def create_session(self) -> str:
        sid = uuid.uuid4().hex
        self._messages[sid] = []
        return sid

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str | None,
        tool_calls: list[ToolCall] | None = None,
        tool_call_id: str | None = None,
        name: str | None = None,
    ) -> None:
        self._messages.setdefault(session_id, []).append(
            ChatMessage(
                role=role,
                content=content,
                tool_call_id=tool_call_id,
                name=name,
                tool_calls=tool_calls,
            )
        )

    def messages(self, session_id: str) -> list[ChatMessage]:
        return list(self._messages.get(session_id, ()))

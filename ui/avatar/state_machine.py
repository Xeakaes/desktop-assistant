"""Pure event→avatar-state reducer (spec §4.1: animation never drives the agent)."""

from __future__ import annotations

from typing import Literal

AvatarState = Literal["idle", "thinking", "working", "speaking", "error"]

_TRANSITIONS: dict[str, AvatarState] = {
    "agent_started": "thinking",
    "tool_started": "working",
    "tool_finished": "working",
    "confirmation_requested": "working",
    "assistant_message": "speaking",
    "agent_finished": "idle",
    "agent_cancelled": "idle",
    "agent_error": "error",
    "error_timeout": "idle",
}


def reduce_event(current: AvatarState, event_name: str) -> AvatarState:
    return _TRANSITIONS.get(event_name, current)

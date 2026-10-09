"""Tool interface shared by every registered tool (spec §3.2)."""

from __future__ import annotations

from dataclasses import dataclass

from core.agent.cancellation import CancellationToken


@dataclass
class ToolResult:
    ok: bool
    data: dict | None = None
    error: str | None = None
    error_code: str | None = None


class Tool:
    name: str
    description: str
    input_schema: dict

    def execute(self, arguments: dict, cancel: CancellationToken) -> ToolResult:
        raise NotImplementedError

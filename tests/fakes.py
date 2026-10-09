"""Scripted fakes for contract tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.agent.cancellation import CancellationToken
from core.providers.base import (
    ChatMessage,
    ModelProvider,
    ProviderResponse,
)
from core.tools.base import Tool, ToolResult


@dataclass
class RecordedCall:
    messages: list[ChatMessage]
    schemas: list[dict]


class FakeProvider(ModelProvider):
    supports_tools = True

    def __init__(self, responses: list, delay_each_s: float = 0.0) -> None:
        self._responses = list(responses)
        self._delay_each_s = delay_each_s
        self.calls: list[RecordedCall] = []

    def complete(self, messages, schemas, cancel: CancellationToken) -> ProviderResponse:
        import time

        if self._delay_each_s:
            time.sleep(self._delay_each_s)
        self.calls.append(RecordedCall(list(messages), list(schemas)))
        if not self._responses:
            raise AssertionError("FakeProvider script exhausted")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeTool(Tool):
    def __init__(self, name: str, results: list[ToolResult] | None = None) -> None:
        self.name = name
        self.description = f"fake tool {name}"
        self.input_schema = {"type": "object", "properties": {}}
        self.calls: list[dict] = []
        self._results = list(results or [ToolResult(ok=True)])

    def execute(self, arguments: dict, cancel: CancellationToken) -> ToolResult:
        self.calls.append(dict(arguments))
        if self._results:
            return self._results.pop(0)
        return ToolResult(ok=True)

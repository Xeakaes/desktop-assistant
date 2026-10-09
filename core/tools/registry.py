"""Permission policy and tool registry (spec §3.1 permission semantics)."""

from __future__ import annotations

from enum import Enum

from core.config import ConfigError
from core.tools.base import Tool


class PermissionLevel(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class PermissionPolicy:
    def __init__(self, levels: dict[str, str] | None = None) -> None:
        self._levels: dict[str, PermissionLevel] = {}
        for name, value in (levels or {}).items():
            try:
                self._levels[name] = PermissionLevel(value)
            except ValueError as exc:
                raise ConfigError(f"invalid permission level for {name!r}: {value!r}") from exc

    def check(self, tool_name: str) -> PermissionLevel:
        if tool_name in self._levels:
            return self._levels[tool_name]
        wildcard = self._levels.get("*")
        return wildcard if wildcard is not None else PermissionLevel.ASK


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]

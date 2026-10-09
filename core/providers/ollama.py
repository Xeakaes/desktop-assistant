"""Ollama chat provider (local models, OpenAI-adjacent but distinct wire format)."""

from __future__ import annotations

import json

import requests

from core.agent.cancellation import CancellationToken
from core.providers.base import (
    ChatMessage,
    ModelProvider,
    ProviderError,
    ProviderResponse,
    ToolCall,
)


def to_provider_tools(schemas: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s.get("description", ""),
                "parameters": s.get("input_schema", {"type": "object"}),
            },
        }
        for s in schemas
    ]


def serialize_messages(messages: list[ChatMessage]) -> list[dict]:
    wire: list[dict] = []
    for m in messages:
        item: dict = {"role": m.role, "content": m.content}
        if m.role == "assistant" and m.tool_calls:
            item["tool_calls"] = [
                {"function": {"name": c.name, "arguments": c.arguments}}
                for c in m.tool_calls
            ]
        if m.role == "tool":
            item["tool_call_id"] = m.tool_call_id
            if m.name:
                item["name"] = m.name
        wire.append(item)
    return wire


def _parse_arguments(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ProviderError(
                f"invalid tool arguments JSON: {exc}", error_code="invalid_arguments"
            ) from exc
        if not isinstance(parsed, dict):
            raise ProviderError("tool arguments must be an object", error_code="invalid_arguments")
        return parsed
    if raw is None:
        return {}
    raise ProviderError(f"unsupported arguments type: {type(raw)}", error_code="invalid_arguments")


class OllamaProvider(ModelProvider):
    supports_tools = True

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_s: float = 60.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        self._session = session or requests.Session()

    def complete(
        self,
        messages: list[ChatMessage],
        schemas: list[dict],
        cancel: CancellationToken,
    ) -> ProviderResponse:
        body: dict = {
            "model": self.model,
            "messages": serialize_messages(messages),
            "stream": False,
        }
        tools = to_provider_tools(schemas)
        if tools:
            body["tools"] = tools
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            resp = self._session.post(
                f"{self.base_url}/api/chat",
                json=body,
                timeout=self.timeout_s,
                headers=headers or None,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.Timeout as exc:
            raise ProviderError(str(exc), error_code="timeout") from exc
        except requests.RequestException as exc:
            raise ProviderError(str(exc), error_code="provider_error") from exc
        message = payload.get("message") or {}
        text = message.get("content")
        tool_calls: list[ToolCall] = []
        for i, raw in enumerate(message.get("tool_calls") or []):
            fn = raw.get("function") or {}
            tool_calls.append(
                ToolCall(
                    id=f"ollama_{i}",
                    name=fn.get("name", ""),
                    arguments=_parse_arguments(fn.get("arguments")),
                )
            )
        if not tool_calls and text:
            # Some models (e.g. qwen via Ollama) emit the tool call as a JSON
            # object in content instead of the native tool_calls field.
            stripped = text.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    embedded = json.loads(stripped)
                except json.JSONDecodeError:
                    embedded = None
                if isinstance(embedded, dict) and "name" in embedded and "arguments" in embedded:
                    tool_calls.append(
                        ToolCall(
                            id="ollama_0",
                            name=embedded["name"],
                            arguments=_parse_arguments(embedded.get("arguments")),
                        )
                    )
                    text = None
        return ProviderResponse(text=text, tool_calls=tool_calls)

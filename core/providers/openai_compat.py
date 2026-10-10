"""OpenAI-compatible chat completions provider (API-hosted models)."""

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
from core.providers.ollama import _parse_arguments


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
        if m.images:
            # Vision: content becomes a list of parts (text + image_url).
            parts: list[dict] = [{"type": "text", "text": m.content or ""}]
            for uri in m.images:
                parts.append({"type": "image_url", "image_url": {"url": uri}})
            item: dict = {"role": m.role, "content": parts}
        else:
            item = {"role": m.role, "content": m.content}
        if m.role == "assistant" and m.tool_calls:
            item["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {
                        "name": c.name,
                        "arguments": json.dumps(c.arguments),
                    },
                }
                for c in m.tool_calls
            ]
        if m.role == "tool":
            item["tool_call_id"] = m.tool_call_id
            if m.name:
                item["name"] = m.name
        wire.append(item)
    return wire


class OpenAICompatProvider(ModelProvider):
    supports_tools = True
    supports_vision = True

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 60.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
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
        }
        tools = to_provider_tools(schemas)
        if tools:
            body["tools"] = tools
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = self._session.post(
                f"{self.base_url}/chat/completions",
                json=body,
                timeout=self.timeout_s,
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.Timeout as exc:
            raise ProviderError(str(exc), error_code="timeout") from exc
        except requests.RequestException as exc:
            raise ProviderError(str(exc), error_code="provider_error") from exc
        try:
            message = payload["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("malformed provider response", error_code="provider_error") from exc
        tool_calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            fn = raw.get("function") or {}
            tool_calls.append(
                ToolCall(
                    id=raw.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=_parse_arguments(fn.get("arguments")),
                )
            )
        return ProviderResponse(text=message.get("content"), tool_calls=tool_calls)

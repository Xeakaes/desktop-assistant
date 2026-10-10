"""OpenAI-compatible chat completions provider (API-hosted models)."""

from __future__ import annotations

import json
import random

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


def serialize_messages(
    messages: list[ChatMessage], include_images: bool = True
) -> list[dict]:
    wire: list[dict] = []
    for m in messages:
        if m.images and include_images:
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


def _looks_like_image_error(text: str) -> bool:
    """Heuristic: did the 400 come from the image parts, not e.g. schema/context?"""
    lowered = text.lower()
    return any(
        key in lowered
        for key in ("image", "vision", "multimodal", "image_url", "base64")
    )


# Hosted providers (Groq above all) answer 429/529 when a burst of tool-calls
# trips the per-minute request limit. The window clears within seconds, so a
# short backoff-and-retry keeps a task alive instead of aborting it with a raw
# HTTP error the user cannot act on.
_RATE_LIMIT_STATUSES = frozenset({429, 529})
_MAX_RATE_RETRIES = 3
_RETRY_AFTER_CAP_S = 30.0


def _rate_limit_delay(resp, attempt: int) -> float:
    """Seconds to wait before retrying a rate-limited (429/529) response."""
    raw = resp.headers.get("Retry-After")
    if raw:
        try:
            return min(max(float(raw), 0.0), _RETRY_AFTER_CAP_S)
        except ValueError:
            pass
    # Exponential backoff with jitter: ~0.5-1s, ~1-2s, ~2-4s.
    base = min(2 ** attempt, _RETRY_AFTER_CAP_S)
    return base * (0.5 + random.random())


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
        supports_vision: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s
        self._session = session or requests.Session()
        self.supports_vision = supports_vision
        self._notice: dict | None = None

    def pop_notice(self) -> dict | None:
        """One-shot UI notice set by complete() (e.g. vision fallback)."""
        notice, self._notice = self._notice, None
        return notice

    def _post_chat(
        self,
        body: dict,
        headers: dict,
        cancel: CancellationToken,
    ):
        """POST /chat/completions, retrying transient rate limits.

        429/529 responses clear within seconds, so we back off (honouring a
        Retry-After header when present) and retry rather than aborting the
        task with a raw HTTP error. Retrying stops immediately if the task is
        cancelled, and the final failure surfaces a human message instead of
        the provider URL.
        """
        attempt = 0
        while True:
            resp = self._session.post(
                f"{self.base_url}/chat/completions",
                json=body,
                timeout=self.timeout_s,
                headers=headers,
            )
            if resp.status_code in _RATE_LIMIT_STATUSES:
                if attempt >= _MAX_RATE_RETRIES:
                    raise ProviderError(
                        "rate limit reached (429); please wait a moment and retry",
                        error_code="rate_limited",
                    )
                # cancel.wait() doubles as a cancel-aware sleep.
                if cancel.wait(_rate_limit_delay(resp, attempt)):
                    raise ProviderError("cancelled", error_code="cancelled")
                attempt += 1
                continue
            return resp

    def complete(
        self,
        messages: list[ChatMessage],
        schemas: list[dict],
        cancel: CancellationToken,
    ) -> ProviderResponse:
        body: dict = {
            "model": self.model,
            "messages": self._serialize(messages),
        }
        tools = to_provider_tools(schemas)
        if tools:
            body["tools"] = tools
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = self._post_chat(body, headers, cancel)
            if (
                resp.status_code == 400
                and self.supports_vision
                and any(m.images for m in messages)
                and _looks_like_image_error(resp.text)
            ):
                # Text-only models reject image_url parts with a 400 mentioning
                # images. Retry once without images and disable vision for the
                # session. Other 400s (context length, bad tool schema) must
                # surface unchanged.
                self.supports_vision = False
                self._notice = {"code": "vision_disabled", "model": self.model}
                body["messages"] = self._serialize(messages, include_images=False)
                resp = self._post_chat(body, headers, cancel)
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

    def _serialize(
        self, messages: list[ChatMessage], include_images: bool | None = None
    ) -> list[dict]:
        if include_images is None:
            include_images = self.supports_vision
        return serialize_messages(messages, include_images=include_images)

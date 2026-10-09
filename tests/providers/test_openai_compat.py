import json
import pytest
import requests
from core.agent.cancellation import CancellationToken
from core.providers.base import ChatMessage, ProviderError
from core.providers.openai_compat import OpenAICompatProvider


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.posts = []

    def post(self, url, json=None, timeout=None, headers=None):
        self.posts.append({"url": url, "json": json, "timeout": timeout, "headers": headers})
        if self.exc:
            raise self.exc
        return self.response


def _msgs():
    return [ChatMessage(role="user", content="hi")]


def _payload(content=None, tool_calls=None):
    message = {"content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {"choices": [{"message": message}]}


def test_openai_parses_tool_call_json_string_args():
    wire_calls = [{
        "id": "call_1",
        "type": "function",
        "function": {"name": "echo", "arguments": json.dumps({"x": 1})},
    }]
    session = FakeSession(FakeResponse(_payload(tool_calls=wire_calls)))
    p = OpenAICompatProvider("http://api", "key", "model", session=session)
    r = p.complete(_msgs(), [], CancellationToken())
    assert r.tool_calls[0].id == "call_1"
    assert r.tool_calls[0].name == "echo"
    assert r.tool_calls[0].arguments == {"x": 1}
    assert session.posts[0]["headers"]["Authorization"] == "Bearer key"


def test_openai_parses_content_text():
    session = FakeSession(FakeResponse(_payload(content="Merhaba")))
    p = OpenAICompatProvider("http://api", "key", "model", session=session)
    r = p.complete(_msgs(), [], CancellationToken())
    assert r.text == "Merhaba" and r.tool_calls == []


def test_openai_http_timeout_maps_error_code():
    session = FakeSession(exc=requests.Timeout("boom"))
    p = OpenAICompatProvider("http://api", "key", "model", timeout_s=9.0, session=session)
    with pytest.raises(ProviderError) as ei:
        p.complete(_msgs(), [], CancellationToken())
    assert ei.value.error_code == "timeout"
    assert session.posts[0]["timeout"] == 9.0


def test_openai_http_error_maps_provider_error():
    session = FakeSession(FakeResponse({}, status_code=500))
    p = OpenAICompatProvider("http://api", "key", "model", session=session)
    with pytest.raises(ProviderError) as ei:
        p.complete(_msgs(), [], CancellationToken())
    assert ei.value.error_code == "provider_error"

"""Regression tests for final-review findings C1, I1–I6."""

import threading
import time

from core.agent.runtime import AgentRuntime
from core.agent.config import AgentConfig
from core.events import EventBus
from core.providers.base import (
    ChatMessage,
    ProviderResponse,
    ToolCall,
)
from core.session.store import SessionStore
from core.tools.base import ToolResult
from core.tools.registry import PermissionPolicy, ToolRegistry
from tests.fakes import FakeProvider, FakeTool


def _runtime(provider, tool=None, policy=None, events=None, config=None):
    reg = ToolRegistry()
    if tool:
        reg.register(tool)
    events = events or EventBus()
    rt = AgentRuntime(
        provider, reg, policy or PermissionPolicy({"*": "allow"}),
        events, SessionStore(), config or AgentConfig(),
    )
    return rt, events


def _assert_history_closed(rt, session_id):
    """C1: every assistant tool_call id has a matching tool result message."""
    calls_seen = set()
    results_seen = set()
    for m in rt._session.messages(session_id):
        if m.role == "assistant" and m.tool_calls:
            for c in m.tool_calls:
                calls_seen.add(c.id)
        if m.role == "tool":
            results_seen.add(m.tool_call_id)
    assert calls_seen == results_seen, f"orphaned tool_calls: {calls_seen - results_seen}"


def test_c1_cancel_mid_batch_closes_history():
    tool = FakeTool("slow", ignore_cancel=True, sleep_s=0.2)
    provider = FakeProvider([
        ProviderResponse(text=None, tool_calls=[
            ToolCall(id="c1", name="slow", arguments={}),
            ToolCall(id="c2", name="slow", arguments={}),
        ]),
        ProviderResponse(text="never", tool_calls=[]),
    ])
    rt, events = _runtime(provider, tool)
    sid = "s1"
    task_id = rt.begin_task(sid, "go")
    th = threading.Thread(target=rt.run_task, args=(task_id,), daemon=True)
    th.start()
    deadline = time.time() + 2.0
    while not tool.calls and time.time() < deadline:
        time.sleep(0.01)
    rt.cancel_task(task_id)
    th.join(timeout=3.0)
    _assert_history_closed(rt, sid)


def test_c1_max_limit_closes_history():
    tool = FakeTool("echo")
    responses = [
        ProviderResponse(text=None, tool_calls=[ToolCall(id=f"c{i}", name="echo", arguments={})])
        for i in range(11)
    ]
    rt, _ = _runtime(provider := FakeProvider(responses), tool,
                     config=AgentConfig(max_tool_calls=10))
    sid = "s1"
    rt.start_task(sid, "loop")
    _assert_history_closed(rt, sid)


def test_i1_parse_error_tool_call_fed_back_not_fatal():
    call = ToolCall(id="c1", name="echo", arguments={})
    call.parse_error = "invalid JSON"
    provider = FakeProvider([
        ProviderResponse(text=None, tool_calls=[call]),
        ProviderResponse(text="Anlaşıldım.", tool_calls=[]),
    ])
    tool = FakeTool("echo")
    rt, _ = _runtime(provider, tool)
    sid = "s1"
    rt.start_task(sid, "echo")
    assert tool.calls == []  # never executed with broken args
    assert "invalid_arguments" in provider.calls[1].messages[-1].content
    _assert_history_closed(rt, sid)


def test_i2_non_serializable_data_does_not_crash():
    class WeirdTool(FakeTool):
        def execute(self, arguments, cancel):
            self.calls.append(dict(arguments))
            return ToolResult(ok=True, data={"s": {1, 2}, "p": object()})

    tool = WeirdTool("weird")
    provider = FakeProvider([
        ProviderResponse(text=None, tool_calls=[ToolCall(id="c1", name="weird", arguments={})]),
        ProviderResponse(text="ok", tool_calls=[]),
    ])
    rt, events = _runtime(provider, tool)
    errs = []
    events.subscribe("agent_error", errs.append)
    finished = []
    events.subscribe("agent_finished", finished.append)
    rt.start_task("s1", "weird")
    assert errs == []
    assert finished and finished[0].payload["final_text"] == "ok"


def test_i3_tool_timeout_fed_back_and_token_cancelled():
    cancel_seen = []

    class SlowTool(FakeTool):
        def execute(self, arguments, cancel):
            self.calls.append(dict(arguments))
            deadline = time.time() + 2.0
            while time.time() < deadline:
                if cancel.cancelled:
                    cancel_seen.append(True)
                    return ToolResult(ok=False, error="stopped", error_code="cancelled")
                time.sleep(0.02)
            return ToolResult(ok=True, data={"late": True})

    tool = SlowTool("slow")
    provider = FakeProvider([
        ProviderResponse(text=None, tool_calls=[ToolCall(id="c1", name="slow", arguments={})]),
        ProviderResponse(text="timeout oldu", tool_calls=[]),
    ])
    rt, _ = _runtime(provider, tool, config=AgentConfig(tool_timeout_s=0.15))
    rt.start_task("s1", "slow")
    assert "timeout" in provider.calls[1].messages[-1].content
    time.sleep(0.3)
    assert cancel_seen, "tool token was not cancelled on timeout"


def test_i6_close_shuts_down_and_prunes_tasks():
    rt, _ = _runtime(FakeProvider([ProviderResponse(text="x", tool_calls=[])]))
    rt.start_task("s1", "hi")
    assert rt._tasks == {}  # completed tasks are pruned
    assert rt.active_task_id is None
    rt.close()
    rt.close()  # idempotent


def test_i5_embedded_json_with_unknown_name_stays_text():
    from core.providers.ollama import OllamaProvider
    from core.agent.cancellation import CancellationToken

    class R:
        status_code = 200
        def json(self):
            return {"message": {"content": '{"name": "not_a_real_tool", "arguments": {}}'}, "done": True}
        def raise_for_status(self):
            pass

    class S:
        def post(self, *a, **k):
            return R()

    p = OllamaProvider("http://x", "m", session=S())
    schemas = [{"name": "screenshot", "description": "d", "input_schema": {"type": "object"}}]
    r = p.complete([ChatMessage(role="user", content="hi")], schemas, CancellationToken())
    assert r.tool_calls == []
    assert r.text is not None

from core.agent.runtime import AgentRuntime
from core.agent.config import AgentConfig
from core.events import EventBus
from core.providers.base import ProviderResponse, ToolCall
from core.session.store import SessionStore
from core.tools.base import ToolResult
from core.tools.registry import ToolRegistry, PermissionPolicy
from tests.fakes import FakeProvider, FakeTool


def _runtime(provider, tool=None, policy=None, events=None):
    reg = ToolRegistry()
    if tool:
        reg.register(tool)
    events = events or EventBus()
    rt = AgentRuntime(
        provider, reg, policy or PermissionPolicy({"*": "allow"}),
        events, SessionStore(), AgentConfig(),
    )
    return rt, events


def test_plain_text_no_tools():
    tool = FakeTool("t", [ToolResult(ok=True)])
    provider = FakeProvider([ProviderResponse(text="Merhaba!", tool_calls=[])])
    rt, events = _runtime(provider, tool)
    seen = []
    events.subscribe("*", seen.append)
    rt.start_task("s1", "selam")
    names = [e.name for e in seen]
    assert "agent_started" in names and "assistant_message" in names and "agent_finished" in names
    assert "tool_started" not in names
    assert tool.calls == []


def test_tool_call_result_fed_back_then_final():
    tool = FakeTool("echo", [ToolResult(ok=True, data={"v": 1})])
    provider = FakeProvider([
        ProviderResponse(text=None, tool_calls=[ToolCall(id="c1", name="echo", arguments={"x": 1})]),
        ProviderResponse(text="Cevap: 1", tool_calls=[]),
    ])
    rt, events = _runtime(provider, tool)
    finished = []
    events.subscribe("agent_finished", finished.append)
    rt.start_task("s1", "echola")
    assert tool.calls == [{"x": 1}]
    assert len(provider.calls) == 2
    second = provider.calls[1].messages
    assert second[-2].role == "assistant" and second[-2].tool_calls is not None
    assert second[-2].tool_calls[0].id == "c1" and second[-2].tool_calls[0].name == "echo"
    assert second[-1].role == "tool" and second[-1].tool_call_id == "c1"
    assert '"v"' in second[-1].content or "v" in second[-1].content
    assert finished[0].payload["final_text"] == "Cevap: 1"


def test_permission_deny_returns_denied_to_model():
    tool = FakeTool("danger", [ToolResult(ok=True)])
    provider = FakeProvider([
        ProviderResponse(text=None, tool_calls=[ToolCall(id="c1", name="danger", arguments={})]),
        ProviderResponse(text="Tamam, yapmadım.", tool_calls=[]),
    ])
    rt, _ = _runtime(provider, tool, policy=PermissionPolicy({"*": "deny"}))
    rt.start_task("s1", "tehlikeli iş")
    assert tool.calls == []
    tool_msg = provider.calls[1].messages[-1]
    assert tool_msg.role == "tool" and "denied" in tool_msg.content.lower()


def test_ask_approved_executes():
    tool = FakeTool("shot", [ToolResult(ok=True, data={"path": "x.png"})])
    provider = FakeProvider([
        ProviderResponse(text=None, tool_calls=[ToolCall(id="c1", name="shot", arguments={})]),
        ProviderResponse(text="Oldu.", tool_calls=[]),
    ])
    rt, events = _runtime(provider, tool, policy=PermissionPolicy({"*": "ask"}))
    reqs = []
    events.subscribe("confirmation_requested", reqs.append)

    def auto_approve(e):
        rt.resolve_confirmation(e.task_id, e.payload["confirm_id"], True)

    events.subscribe("confirmation_requested", auto_approve)
    rt.start_task("s1", "ekran görüntüsü al")
    assert tool.calls == [{}]
    assert reqs[0].payload["tool_name"] == "shot"


def test_ask_denied_never_executes():
    tool = FakeTool("shot", [ToolResult(ok=True)])
    provider = FakeProvider([
        ProviderResponse(text=None, tool_calls=[ToolCall(id="c1", name="shot", arguments={})]),
        ProviderResponse(text="Anlaşıldı.", tool_calls=[]),
    ])
    rt, events = _runtime(provider, tool, policy=PermissionPolicy({"*": "ask"}))
    events.subscribe(
        "confirmation_requested",
        lambda e: rt.resolve_confirmation(e.task_id, e.payload["confirm_id"], False),
    )
    rt.start_task("s1", "ekran görüntüsü al")
    assert tool.calls == []
    assert "permission_denied" in provider.calls[1].messages[-1].content

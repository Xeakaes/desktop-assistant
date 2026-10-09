# Desktop AI Assistant — M0 "Engine Runs" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the headless agent core: event bus, permissioned tool registry, agent loop with real cancellation mechanics, Ollama + OpenAI-compatible providers, a screen-control adapter, and a CLI that proves "user text → model → tool → result back to model → final answer" end-to-end.

**Architecture:** Pure-Python `core/` package (no Qt). The runtime consumes a `ModelProvider` and a `ToolRegistry`; every tool call passes a `PermissionPolicy` check in code; tool results always return to the model. UI is out of scope for M0 except a temporary CLI. Spec: `docs/specs/2026-10-09-desktop-assistant-design.md`.

**Tech Stack:** Python 3.12+, `requests` (providers + screen-control SDK), `pytest` (dev). Git repo at `/home/xeakaes/desktop-assistant`.

**Spec:** `/home/xeakaes/desktop-assistant/docs/specs/2026-10-09-desktop-assistant-design.md`

## Global Constraints

- `core/` must not import Qt or any UI library.
- `ToolResult` fields exactly: `ok: bool`, `data: dict | None`, `error: str | None`, `error_code: str | None` (spec §3.2).
- Agent defaults (overridable via `config/settings.json`): `max_tool_calls=10`, `tool_timeout_s=30`, `model_timeout_s=60` (spec §3.1).
- Every event carries `session_id` and `task_id` (spec §3.4).
- Secrets live only in `config/secrets.json` with file mode `0600`; never logged (spec §3.7).
- Screen-control adapter transport: existing SDK at `/home/xeakaes/screen-control/sdk/screen_control.py` (HTTP client to `127.0.0.1:8745`); inject a client factory so tests never need a live server.
- No feature work beyond M0 scope (no avatar, no SQLite, no voice).

## Review Focus

Failure modes most likely to bite a real user; each is pinned to a task below:

1. **Tool-call history replay differs between Ollama and OpenAI wire formats** (assistant `tool_calls` must survive into the next request) → Task 6 `test_ollama_replays_assistant_tool_calls_history`, `test_openai_replays_assistant_tool_calls_history`, `test_internal_schema_to_provider_tools`; Task 4 `test_tool_call_result_fed_back_then_final` asserts history shape end-to-end.
2. **Ask-confirmation race:** approval fires inside `publish` before a waiter exists → Task 4 registers the pending record **before** publishing; Task 5 `test_stale_confirm_id_ignored`, `test_double_reply_second_ignored`, `test_cancel_while_confirmation_pending_blocks_late_approval`.
3. **Cancellation ignored during a blocking HTTP call or non-cancellable tool** → providers and the adapter set explicit timeouts (Tasks 6–7); runtime discards late results after cancel (Task 5 `test_cancel_discards_late_tool_result`); `test_cancel_mid_loop` pins abandoned in-flight provider responses.
4. **Denied tool still executes** → Task 4 `test_ask_denied_never_executes` asserts the fake tool recorded zero calls.
5. **Malformed/limit conditions loop forever** → Task 5 `test_invalid_arguments_fed_back_then_final`, `test_unknown_tool_name`, `test_max_tool_call_limit`.

---

### Task 1: Project skeleton, git, config loading

**Files:**
- Create: `requirements.txt`, `.gitignore`, `cli.py` (stub), `core/__init__.py`, `core/config.py`, `config/settings.json`, `config/secrets.json`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `core.config.load_settings(path: Path) -> dict`, `core.config.load_secrets(path: Path) -> dict`, `core.config.ensure_secrets_mode(path: Path) -> None` (raises `ConfigError` if mode is not `0o600`).

- [ ] **Step 1: Init repo and skeleton**

```bash
cd /home/xeakaes/desktop-assistant
git init
printf 'requests>=2.31\npytest>=8.0\n' > requirements.txt
printf '__pycache__/\n.venv/\n*.pyc\nconfig/secrets.json\n' > .gitignore
mkdir -p core tests config
touch core/__init__.py tests/__init__.py
python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

- [ ] **Step 2: Write failing config tests**

`tests/test_config.py`:

```python
import json, os, stat
from pathlib import Path
import pytest
from core.config import load_settings, load_secrets, ensure_secrets_mode, ConfigError

def test_load_settings_reads_json(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"agent": {"max_tool_calls": 5}}))
    assert load_settings(p)["agent"]["max_tool_calls"] == 5

def test_load_secrets_reads_json(tmp_path):
    p = tmp_path / "secrets.json"
    p.write_text(json.dumps({"screen_control_api_key": "k"}))
    os.chmod(p, 0o600)
    assert load_secrets(p)["screen_control_api_key"] == "k"

def test_ensure_secrets_mode_rejects_world_readable(tmp_path):
    p = tmp_path / "secrets.json"
    p.write_text("{}")
    os.chmod(p, 0o644)
    with pytest.raises(ConfigError):
        ensure_secrets_mode(p)

def test_default_settings_values(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({}))
    s = load_settings(p)
    assert s["agent"] == {"max_tool_calls": 10, "tool_timeout_s": 30, "model_timeout_s": 60}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_config.py -v` → FAIL (ImportError `core.config`).

- [ ] **Step 4: Implement `core/config.py`**

`ConfigError(Exception)`; `load_settings` fills agent defaults from Global Constraints when missing; `load_secrets` reads JSON; `ensure_secrets_mode` checks `stat.S_IMODE(path.stat().st_mode) == 0o600`. Write default `config/settings.json` (provider ollama `http://127.0.0.1:11434`, model `llama3.2`, screen_control `127.0.0.1:8745`, permissions `{"*": "ask"}`) and `config/secrets.json` (`{}` then `chmod 600`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_config.py -v` → 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: project skeleton and config loading"
```

---

### Task 2: CancellationToken and EventBus

**Files:**
- Create: `core/agent/__init__.py`, `core/agent/cancellation.py`, `core/events.py`
- Test: `tests/test_cancellation.py`, `tests/test_events.py`

**Interfaces:**
- Produces:
  - `core.agent.cancellation.CancellationToken` — `.cancel() -> None`, `.cancelled -> bool` (property), `.raise_if_cancelled() -> None` (raises `TaskCancelled`), `.wait(timeout: float) -> bool` (True if cancelled within timeout).
  - `core.agent.cancellation.TaskCancelled(Exception)`
  - `core.events.Event` dataclass — `name: str`, `session_id: str`, `task_id: str`, `payload: dict`
  - `core.events.EventBus` — `.subscribe(name: str, cb: Callable[[Event], None]) -> None`, `.unsubscribe(name, cb) -> None`, `.publish(name, session_id, task_id, payload) -> None` (also supports `subscribe("*", cb)`).

- [ ] **Step 1: Write failing cancellation tests**

`tests/test_cancellation.py`:

```python
import threading, time
from core.agent.cancellation import CancellationToken, TaskCancelled
import pytest

def test_initial_not_cancelled():
    assert CancellationToken().cancelled is False

def test_cancel_sets_flag():
    t = CancellationToken(); t.cancel(); assert t.cancelled is True

def test_raise_if_cancelled():
    t = CancellationToken(); t.cancel()
    with pytest.raises(TaskCancelled): t.raise_if_cancelled()

def test_wait_returns_false_on_timeout():
    assert CancellationToken().wait(0.05) is False

def test_wait_returns_true_when_cancelled_from_thread():
    t = CancellationToken()
    threading.Timer(0.05, t.cancel).start()
    assert t.wait(1.0) is True
```

- [ ] **Step 2: Write failing event bus tests**

`tests/test_events.py`:

```python
from core.events import EventBus, Event

def test_publish_delivers_with_ids():
    bus = EventBus(); seen = []
    bus.subscribe("agent_started", seen.append)
    bus.publish("agent_started", "s1", "t1", {"user_text": "hi"})
    assert seen == [Event("agent_started", "s1", "t1", {"user_text": "hi"})]

def test_wildcard_receives_all():
    bus = EventBus(); names = []
    bus.subscribe("*", lambda e: names.append(e.name))
    bus.publish("a", "s", "t", {}); bus.publish("b", "s", "t", {})
    assert names == ["a", "b"]

def test_unsubscribe_stops_delivery():
    bus = EventBus(); seen = []
    cb = seen.append
    bus.subscribe("x", cb); bus.unsubscribe("x", cb)
    bus.publish("x", "s", "t", {})
    assert seen == []

def test_event_name_list_matches_spec():
    from core.events import EVENT_NAMES
    assert set(EVENT_NAMES) >= {
        "agent_started", "assistant_message", "tool_started", "tool_finished",
        "confirmation_requested", "agent_error", "agent_finished", "agent_cancelled"}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cancellation.py tests/test_events.py -v` → FAIL (imports).

- [ ] **Step 4: Implement**

`core/agent/cancellation.py`: thread-safe flag (`threading.Event` under the hood). `core/events.py`: `EVENT_NAMES` tuple per spec §3.4 plus `confirmation_requested`; `EventBus` stores `dict[str, list[Callable]]`, publish iterates a snapshot of subscribers (safe if a callback unsubscribes).

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cancellation.py tests/test_events.py -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: cancellation token and event bus"
```

---

### Task 3: Tool interface, PermissionPolicy, ToolRegistry

**Files:**
- Create: `core/tools/__init__.py`, `core/tools/base.py`, `core/tools/registry.py`
- Test: `tests/tools/test_base.py`, `tests/tools/test_registry.py`

**Interfaces:**
- Consumes: `CancellationToken` (Task 2).
- Produces:
  - `core.tools.base.ToolResult` — fields per Global Constraints.
  - `core.tools.base.Tool` — attrs `name: str`, `description: str`, `input_schema: dict`; method `execute(self, arguments: dict, cancel: CancellationToken) -> ToolResult`.
  - `core.tools.registry.PermissionLevel` — `ALLOW | ASK | DENY` (str enum: `"allow" | "ask" | "deny"`).
  - `core.tools.registry.PermissionPolicy` — `__init__(self, levels: dict[str, str] | None = None)`; `*` is the wildcard default (fallback `ask`); `.check(self, tool_name: str) -> PermissionLevel`.
  - `core.tools.registry.ToolRegistry` — `.register(tool: Tool) -> None` (duplicate name → `ValueError`), `.get(name) -> Tool | None`, `.names() -> list[str]`, `.schemas() -> list[dict]` (name/description/input_schema for the provider).

- [ ] **Step 1: Write failing ToolResult/Tool tests**

`tests/tools/test_base.py`:

```python
from dataclasses import fields
from core.tools.base import ToolResult, Tool
from core.agent.cancellation import CancellationToken

def test_toolresult_field_names():
    assert [f.name for f in fields(ToolResult)] == ["ok", "data", "error", "error_code"]

def test_tool_is_abstract_shape():
    class T(Tool):
        name = "t"; description = "d"; input_schema = {"type": "object"}
        def execute(self, arguments, cancel):
            return ToolResult(ok=True, data={"echo": arguments})
    r = T().execute({"a": 1}, CancellationToken())
    assert r.ok and r.data == {"a": 1} and r.error is None and r.error_code is None
```

- [ ] **Step 2: Write failing policy/registry tests**

`tests/tools/test_registry.py`:

```python
import pytest
from core.tools.base import Tool, ToolResult
from core.tools.registry import PermissionPolicy, PermissionLevel, ToolRegistry

class Dummy(Tool):
    name = "dummy"; description = "d"; input_schema = {"type": "object"}
    def __init__(self): self.calls = []
    def execute(self, arguments, cancel):
        self.calls.append(arguments); return ToolResult(ok=True)

def test_policy_wildcard_default_ask():
    assert PermissionPolicy({}).check("anything") is PermissionLevel.ASK

def test_policy_exact_beats_wildcard():
    p = PermissionPolicy({"*": "ask", "screenshot": "allow"})
    assert p.check("screenshot") is PermissionLevel.ALLOW
    assert p.check("mouse") is PermissionLevel.ASK

def test_policy_deny():
    p = PermissionPolicy({"*": "deny"})
    assert p.check("x") is PermissionLevel.DENY

def test_register_duplicate_raises():
    r = ToolRegistry(); r.register(Dummy())
    with pytest.raises(ValueError): r.register(Dummy())

def test_schemas_shape():
    r = ToolRegistry(); r.register(Dummy())
    assert r.schemas() == [{"name": "dummy", "description": "d", "input_schema": {"type": "object"}}]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/tools -v` → FAIL (imports).

- [ ] **Step 4: Implement `core/tools/base.py` and `core/tools/registry.py`**

`Tool.execute` raises `NotImplementedError` by default. Policy maps config dict values through `PermissionLevel(value)`; unknown value → `ConfigError` from `core.config`. Registry is a `dict[str, Tool]`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/tools -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: tool interface, permission policy, registry"
```

---

### Task 4: AgentRuntime — happy path, deny, ask approve/deny

**Files:**
- Create: `core/agent/runtime.py`, `core/agent/config.py`, `core/session/__init__.py`, `core/session/store.py`, `core/providers/__init__.py` (empty for now), `tests/fakes.py`
- Test: `tests/contract/test_agent_happy_path.py`

**Interfaces:**
- Consumes: Task 2 (`CancellationToken`, `EventBus`), Task 3 (`Tool`, `ToolResult`, `ToolRegistry`, `PermissionPolicy`, `PermissionLevel`).
- Produces:
  - `core.providers.base` stubs **defined in this task** (full provider impl in Task 6):
    - `ToolCall(id: str, name: str, arguments: dict)`
    - `ChatMessage(role: str, content: str | None, tool_call_id: str | None = None, name: str | None = None, tool_calls: list[ToolCall] | None = None)` — **assistant messages that requested tools must carry `tool_calls`** so the next request can replay the full history (assistant call + tool result). `role` ∈ `"user" | "assistant" | "tool"`.
    - `ProviderResponse(text: str | None, tool_calls: list[ToolCall])`
    - `ModelProvider` ABC: `supports_tools: bool` class attr; `complete(self, messages: list[ChatMessage], schemas: list[dict], cancel: CancellationToken) -> ProviderResponse` — `schemas` is `ToolRegistry.schemas()` output (internal shape: `{"name", "description", "input_schema"}`); **each provider converts this to its wire tool format internally** (Task 6 defines `to_provider_tools` per provider; runtime never serializes wire format).
    - `ProviderError(Exception)` — `.error_code: str`, `.message: str` (stub here, used in Task 6).
  - `core.session.store.SessionStore` — `.create_session() -> str` (uuid4 hex), `.add_message(session_id, role, content, tool_calls=None) -> None`, `.messages(session_id) -> list[ChatMessage]`.
  - `core.agent.config.AgentConfig` — `max_tool_calls: int = 10`, `tool_timeout_s: float = 30`, `model_timeout_s: float = 60`.
  - `core.agent.runtime.AgentRuntime` — **task id is created before execution starts** so a caller (CLI signal handler, tests on another thread) can always address the running task:
    - `__init__(self, provider: ModelProvider, registry: ToolRegistry, policy: PermissionPolicy, events: EventBus, session: SessionStore, config: AgentConfig | None = None)`
    - `begin_task(self, session_id: str, user_text: str) -> str` — generates `task_id` (uuid4 hex), registers the task as **active**, appends the user message, returns immediately **without running the loop**.
    - `run_task(self, task_id: str) -> None` — executes the loop synchronously on the calling thread; clears the active task in `finally`.
    - `start_task(self, session_id: str, user_text: str) -> str` — convenience: `begin_task` + `run_task`; returns `task_id` **after** completion (CLI's normal path).
    - `active_task_id: str | None` (property) — set by `begin_task`, cleared when `run_task` finishes.
    - `cancel_active_task(self) -> None` — cancels `active_task_id` if any (used by CLI SIGINT).
    - `resolve_confirmation(self, task_id: str, confirm_id: str, approved: bool) -> None`
    - `cancel_task(self, task_id: str) -> None`
  - `tests/fakes.py`: `FakeProvider(responses: list[ProviderResponse | Exception])` records every `complete()` call (messages, tools); raises if the script is exhausted. `FakeTool(name, results: list[ToolResult])` records `(arguments)` per call.

- [ ] **Step 1: Write failing contract tests (happy path + permissions)**

`tests/contract/test_agent_happy_path.py`:

```python
from core.agent.runtime import AgentRuntime
from core.agent.config import AgentConfig
from core.agent.cancellation import CancellationToken
from core.events import EventBus, Event
from core.providers.base import ProviderResponse, ToolCall, ChatMessage, ModelProvider
from core.session.store import SessionStore
from core.tools.base import Tool, ToolResult
from core.tools.registry import ToolRegistry, PermissionPolicy
from tests.fakes import FakeProvider, FakeTool

def _runtime(provider, tool=None, policy=None, events=None):
    reg = ToolRegistry()
    if tool: reg.register(tool)
    events = events or EventBus()
    rt = AgentRuntime(provider, reg, policy or PermissionPolicy({"*": "allow"}),
                      events, SessionStore(), AgentConfig())
    return rt, events

def test_plain_text_no_tools():
    tool = FakeTool("t", [ToolResult(ok=True)])
    provider = FakeProvider([ProviderResponse(text="Merhaba!", tool_calls=[])])
    rt, events = _runtime(provider, tool)
    seen = []
    events.subscribe("*", seen.append)
    tid = rt.start_task("s1", "selam")
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
    # full history replay: assistant tool_calls message THEN tool result
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
    assert tool.calls == []  # never executed
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
    # resolve immediately by subscribing: simulate UI
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
    events.subscribe("confirmation_requested",
        lambda e: rt.resolve_confirmation(e.task_id, e.payload["confirm_id"], False))
    rt.start_task("s1", "ekran görüntüsü al")
    assert tool.calls == []
    assert "permission_denied" in provider.calls[1].messages[-1].content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/contract/test_agent_happy_path.py -v` → FAIL (imports).

- [ ] **Step 3: Implement SessionStore, provider base stubs, AgentRuntime happy path**

`AgentRuntime` flow (spec §3.1 + review fixes):

- `begin_task` mints `task_id`, sets it active, appends the user message; `run_task` executes the loop; `start_task` is begin+run for the CLI.
- Loop: check token → `provider.complete(messages, registry.schemas(), cancel)` (if `not provider.supports_tools` and registry non-empty → `agent_error` `unsupported_capability`, stop) → if `tool_calls`: append an **assistant `ChatMessage` with `tool_calls` populated** to the session/history (so the next request replays call + result), then for each call:
  - `policy.check` → **ALLOW**: publish `tool_started`, execute with a per-tool token linked to the task token and a wall-clock timeout (`tool_timeout_s`); if the task token is cancelled while the tool is in flight, **discard the tool's late result** (do not feed it to the model) and stop the task.
  - **DENY**: do not execute; feed a `permission_denied` tool message.
  - **ASK**: mint `confirm_id` (uuid4 hex), **create the pending-confirmation record (a `threading.Event` keyed `(task_id, confirm_id)`) BEFORE publishing** `confirmation_requested` — a subscriber that approves synchronously inside the publish call must not race an unregistered waiter; then wait on that event. `resolve_confirmation` resolves the record **atomically** (first reply wins; a second reply for the same `confirm_id` is a no-op); a reply with unknown/stale `confirm_id` or `task_id` is a no-op; cancellation invalidates the record so a late approval never executes.
- After all tool results for a response: append them as `role="tool"` messages and call the provider again. If no tool calls: publish `assistant_message` + `agent_finished`, store the assistant message, clear the active task.
- Tool wall-clock timeout → `ToolResult(ok=False, error="tool timed out", error_code="timeout")`; a tool exception → `error_code="tool_exception"`.
- **Tool cancellation contract (document in the module docstring):** tools receive a `CancellationToken` and must check it before starting and between segments of long work. HTTP `timeout=` bounds connection/read inactivity per requests semantics — it is **not** a hard total-duration cap. Setting the token does **not** stop non-cancellable in-flight work; the runtime's guarantee is only that a cancelled task stops observing that work (late results discarded, no further model calls).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/contract/test_agent_happy_path.py -v` → 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: agent runtime happy path with permission ask/deny"
```

---

### Task 5: AgentRuntime — cancellation, limits, malformed args

**Files:**
- Modify: `core/agent/runtime.py`
- Test: `tests/contract/test_agent_failure_paths.py`

**Interfaces:**
- Consumes: Task 4 interfaces unchanged.
- Produces: same `AgentRuntime` with the failure behaviors below (no signature changes).

- [ ] **Step 1: Write failing failure-path tests**

`tests/contract/test_agent_failure_paths.py` (each test builds a runtime like Task 4). Helpers in `tests/fakes.py`: `FakeProvider(responses, delay_each_s=0.0)` sleeps `delay_each_s` before each scripted response (simulates a slow in-flight HTTP call); `FakeTool` gains `ignore_cancel: bool = False` (when True, `execute` sleeps `sleep_s` without checking the token).

1. `test_cancel_mid_loop` — FakeProvider script: `[ProviderResponse(text="slow", tool_calls=[])]` with `delay_each_s=0.3`. `begin_task` on a worker thread + `run_task`; main thread waits 0.05 s, then `cancel_task(task_id)` (task_id known **before** run, via `begin_task`). Assert: exactly one `agent_cancelled` event; **no** `agent_finished`; **no** `assistant_message` (the in-flight provider response was abandoned, not delivered).
2. `test_cancel_while_confirmation_pending_blocks_late_approval` — policy `ask`; after `confirmation_requested` is observed, `cancel_task`, then `resolve_confirmation(task, confirm_id, True)`; assert `tool.calls == []` and `agent_cancelled` published.
3. `test_stale_confirm_id_ignored` — resolve with `"bogus"` confirm_id first, then the real approve; tool runs **once**.
4. `test_double_reply_second_ignored` — auto-approve callback fires twice for the same `confirm_id`; tool runs once; no exception.
5. `test_invalid_arguments_fed_back_then_final` — **not a retry mechanism:** FakeTool returns `ToolResult(ok=False, error="bad args", error_code="invalid_arguments")`; second provider response is final text; assert the tool ran once and the model received the `invalid_arguments` tool message before the final answer. (Naming matches behavior: error is fed back; the *model* decides what to do next — the runtime does not re-issue the call.)
6. `test_unknown_tool_name` — provider calls `"ghost"` not in registry; runtime feeds `unknown_tool` result; second response final; no crash.
7. `test_max_tool_call_limit` — provider always returns a tool call for `echo`; assert `agent_error` with `payload["error_code"] == "max_tool_calls"` after exactly 10 tool executions.
8. `test_provider_without_tools_fails_fast` — FakeProvider with `supports_tools = False`, registry non-empty; assert `agent_error` payload `error_code == "unsupported_capability"` and `provider.complete` called at most once.
9. `test_cancel_discards_late_tool_result` — FakeTool `ignore_cancel=True`, `sleep_s=0.3`; start task on a thread; cancel while the tool is executing; when `execute` finally returns, assert **no** second `provider.complete` call and `agent_cancelled` published (late result discarded — token alone never claimed to stop the tool).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/contract/test_agent_failure_paths.py -v` → FAIL (missing behaviors).

- [ ] **Step 3: Implement failure behaviors in `runtime.py`**

Wrap `tool.execute` in `try/except Exception` → `tool_exception` result. Pending-confirmation records live in a dict guarded by a lock; `resolve_confirmation` pops the record under the lock (first reply wins — doubles and post-cancel late approvals are no-ops because the record is gone/invalidated). Count tool calls per task; on limit, publish `agent_error` (`payload={"error_code": "max_tool_calls"}`) and stop. `supports_tools` gate before the first `complete` when `registry.names()` is non-empty. Cancellation checks: before `complete`, before each tool, before feeding results; **after a cancelled task, a tool result that arrives late is discarded — never appended to history, never sent to the provider.** Module docstring restates the tool cancellation contract from Task 4 (HTTP timeout ≠ total cap; token ≠ forcible stop).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/contract -v` → all PASS (Tasks 4+5).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: runtime cancellation, limits, malformed tool handling"
```

---

### Task 6: Providers — Ollama and OpenAI-compatible

**Files:**
- Create: `core/providers/base.py` (move/complete the Task 4 stubs), `core/providers/ollama.py`, `core/providers/openai_compat.py`
- Test: `tests/providers/test_ollama.py`, `tests/providers/test_openai_compat.py`, `tests/providers/test_normalization.py`

**Interfaces:**
- Consumes: `ChatMessage` (with `tool_calls`), `ToolCall`, `ProviderResponse`, `ModelProvider`, `ProviderError`, `CancellationToken` (Tasks 2, 4); `ToolRegistry.schemas()` shape `{"name", "description", "input_schema"}` (Task 3).
- Produces:
  - `core.providers.ollama.OllamaProvider(base_url: str, model: str, api_key: str | None = None, timeout_s: float = 60.0, session: requests.Session | None = None)` — `supports_tools = True`. `complete()` POSTs `{base_url}/api/chat` with `stream: false`; converts Ollama `tool_calls` (`{"function": {"name", "arguments"}}` with JSON-string or dict args) into `ToolCall`; HTTP error → `ProviderError(error_code="provider_error"|"timeout")`.
  - `core.providers.openai_compat.OpenAICompatProvider(base_url: str, api_key: str, model: str, timeout_s: float = 60.0, session: requests.Session | None = None)` — `supports_tools = True`. POST `{base_url}/chat/completions`, Bearer auth; normalizes OpenAI `tool_calls` (`function.arguments` JSON string) the same way.
  - **Wire conversion helpers (explicit, tested):**
    - `core.providers.ollama.to_provider_tools(schemas: list[dict]) -> list[dict]` — internal schema → Ollama wire tools.
    - `core.providers.openai_compat.to_provider_tools(schemas: list[dict]) -> list[dict]` — internal schema → OpenAI `{"type": "function", "function": {...}}`.
    - `core.providers.ollama.serialize_messages(messages: list[ChatMessage]) -> list[dict]` and `core.providers.openai_compat.serialize_messages(...)` — **both must replay assistant `tool_calls` history correctly** (Ollama: `tool_calls: [{"function": {"name", "arguments": dict}}]`; OpenAI: `tool_calls: [{"id", "type": "function", "function": {"name", "arguments": json.dumps(dict)}}]`); tool-result messages carry the matching id field each wire format expects.
  - `core.providers.base.ProviderError(Exception)` — `.error_code: str`, `.message: str`.
  - Factory helper `core.providers.create_provider(settings: dict, secrets: dict, session=None) -> ModelProvider` reading `settings["provider"]["type"]` (`"ollama" | "openai_compat"`).

- [ ] **Step 1: Write failing serialization / normalization tests**

`tests/providers/test_normalization.py`:

```python
import json
from core.providers.base import ChatMessage, ToolCall
from core.providers.ollama import serialize_messages as so, to_provider_tools as tpo
from core.providers.openai_compat import serialize_messages as sa, to_provider_tools as tpa

HISTORY = [
    ChatMessage(role="user", content="ekran görüntüsü al"),
    ChatMessage(role="assistant", content=None,
                tool_calls=[ToolCall(id="c1", name="screenshot", arguments={})]),
    ChatMessage(role="tool", content='{"ok": true, "data": {"path": "x.png"}}',
                tool_call_id="c1", name="screenshot"),
]

def test_internal_schema_to_provider_tools():
    schemas = [{"name": "screenshot", "description": "d", "input_schema": {"type": "object", "properties": {}}}]
    o, a = tpo(schemas), tpa(schemas)
    assert o[0]["function"]["name"] == "screenshot"
    assert a[0]["type"] == "function" and a[0]["function"]["name"] == "screenshot"

def test_ollama_replays_assistant_tool_calls_history():
    wire = so(HISTORY)
    assert wire[1]["role"] == "assistant"
    assert wire[1]["tool_calls"][0]["function"]["name"] == "screenshot"
    assert wire[1]["tool_calls"][0]["function"]["arguments"] == {}
    assert wire[2]["role"] == "tool" and wire[2]["tool_call_id"] == "c1"

def test_openai_replays_assistant_tool_calls_history():
    wire = sa(HISTORY)
    assert wire[1]["role"] == "assistant"
    tc = wire[1]["tool_calls"][0]
    assert tc["id"] == "c1" and tc["type"] == "function"
    assert json.loads(tc["function"]["arguments"]) == {}
    assert wire[2]["role"] == "tool" and wire[2]["tool_call_id"] == "c1"
```

- [ ] **Step 2: Write failing Ollama provider tests (mocked HTTP)**

`tests/providers/test_ollama.py` using a fake `requests.Session` (stub `post` returning canned JSON):

1. `test_ollama_parses_tool_call_dict_args` — response `{"message": {"tool_calls": [{"function": {"name": "echo", "arguments": {"x": 1}}}]}, "done": true}` → `ProviderResponse.tool_calls == [ToolCall(id=<generated>, name="echo", arguments={"x": 1})]`.
2. `test_ollama_parses_tool_call_json_string_args` — arguments as `'{"x": 1}'` → same normalized dict.
3. `test_ollama_http_timeout_maps_error_code` — session raises `requests.Timeout` → `ProviderError` with `error_code == "timeout"` and `timeout_s` was passed to `session.post`.
4. `test_ollama_http_error_maps_provider_error` — status 500 → `error_code == "provider_error"`.

Mirror the four tests for `openai_compat` in `tests/providers/test_openai_compat.py` (wire shape: `{"choices": [{"message": {"content": ..., "tool_calls": [{"id": "call_1", "function": {"name": "...", "arguments": "\"{...}\""}}]}}]}`).

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/providers -v` → FAIL.

- [ ] **Step 4: Implement providers + factory**

`complete()` calls `serialize_messages(messages)` and `to_provider_tools(schemas)` internally — the runtime stays wire-agnostic. Ollama tool-call ids: generate `ollama_<index>` per response when the wire omits ids (uniqueness within the response is enough). Both providers pass `timeout=timeout_s` on every request (spec §3.5 — bounds connection/read inactivity; **not** a total-duration cap, per the cancellation contract in Task 4). `create_provider` reads secrets only for API-key fields; never log them.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests -v` → all PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: ollama and openai-compatible providers with normalization"
```

---

### Task 7: screen-control adapter

**Files:**
- Create: `core/tools/screen_control.py`
- Test: `tests/tools/test_screen_control.py`

**Interfaces:**
- Consumes: `Tool`, `ToolResult`, `CancellationToken`.
- Produces: `core.tools.screen_control.register_screen_control(registry: ToolRegistry, client_factory: Callable[[], Any], timeout_s: float = 30.0) -> None` registering exactly these tools (names fixed — models and tests depend on them):
  - `screenshot` — args `{}` or `{"path": str}`; default path under a temp/artifacts dir; returns `{"path": ...}`.
  - `ocr_screen` — args `{}` or `{"scan_focus": bool}`; returns `{"text": str}`.
  - `mouse` — args `{"action": str, "x": int | None, "y": int | None}`.
  - `keyboard` — args `{"action": str, "key": str | None, "text": str | None}`.
  - `list_windows` — args `{}`; returns `{"windows": ...}` (raw SDK payload as JSON-safe dict/list).
  - `focus_window` — args `{"hwnd": int}`.
  Each `execute`: `client = client_factory()`; call the matching SDK method; on `requests.Timeout` → `error_code="timeout"`; on connection error → `server_unreachable`; on SDK error/exception → `tool_exception` or structured server error; check `cancel.cancelled` before calling the client. `input_schema` per JSON Schema, minimal but valid (`type: object` with `properties` and `required`).

- [ ] **Step 1: Write failing adapter tests**

`tests/tools/test_screen_control.py` with `FakeClient` (records method calls, returns canned values, can raise `requests.Timeout` / `requests.ConnectionError`):

1. `test_screenshot_calls_sdk_and_returns_path`
2. `test_mouse_validates_action_and_forwards`
3. `test_timeout_sets_error_code` (`error_code == "timeout"`)
4. `test_connection_error_sets_server_unreachable`
5. `test_cancelled_before_call_does_not_touch_client` (token pre-cancelled; `FakeClient.calls == []`; `error_code == "cancelled"`)
6. `test_registered_names_match_spec` — `{"screenshot", "ocr_screen", "mouse", "keyboard", "list_windows", "focus_window"}`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/tools/test_screen_control.py -v` → FAIL.

- [ ] **Step 3: Implement `core/tools/screen_control.py`**

Import the SDK lazily inside `client_factory` default (tests inject `FakeClient`); do **not** import `/home/xeakaes/screen-control` at module import time. Default factory builds `ScreenControl(host, port, api_key=secrets…)` — the CLI (Task 8) wires it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/tools -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: screen-control tool adapter"
```

---

### Task 8: CLI wiring and live end-to-end verification

**Files:**
- Create: `cli.py` (replace stub), `core/bootstrap.py`
- Test: `tests/test_bootstrap.py`
- Manual: live Ollama + live screen-control server

**Interfaces:**
- Consumes: everything above.
- Produces: `core.bootstrap.build_runtime(settings_path: Path | None = None, secrets_path: Path | None = None, client_factory=None) -> tuple[AgentRuntime, EventBus, SessionStore]` — loads config (Task 1), `ensure_secrets_mode`, `create_provider` (Task 6), registers screen-control tools unless `settings["screen_control"]["enabled"] is False`, builds policy from `settings["permissions"]`, returns wired runtime.

- [ ] **Step 1: Write failing bootstrap test**

`tests/test_bootstrap.py`: `build_runtime` with a temp settings JSON (provider type `ollama`, fake secrets 0600) and injected `client_factory` + fake session; assert runtime is `AgentRuntime`, screen-control names present in `runtime.registry.names()`.

- [ ] **Step 2: Run test to verify it fails; implement `core/bootstrap.py`; test passes**

Run: `.venv/bin/pytest tests/test_bootstrap.py -v` → FAIL then PASS.

- [ ] **Step 3: Implement `cli.py`**

Interactive loop: build runtime; subscribe `*` → print event lines (`[tool_started] echo {...}`, `[assistant_message] ...`); on `confirmation_requested`, prompt `Onaylıyor musun? [e/h]:` and `resolve_confirmation`; on `agent_error` / `agent_cancelled`, print reason. Per user line: `task_id = rt.begin_task(session_id, text)` **first** (id exists before any work), install a SIGINT handler that calls `rt.cancel_active_task()`, then `rt.run_task(task_id)` on the main thread — Ctrl+C mid-task cancels the active task cleanly instead of leaving an uninterruptible call with no addressable id; after run, restore the handler. One session created at startup.

- [ ] **Step 4: Unit suite green**

Run: `.venv/bin/pytest tests -v` → all PASS.

- [ ] **Step 5: Live Ollama smoke (no tools)**

Ensure Ollama is running (`systemctl --user status ollama` or `ollama serve`). Run: `.venv/bin/python cli.py` → send `Merhaba, kısaca kendini tanıt` → expect `assistant_message` + `agent_finished`, no tool events.

- [ ] **Step 6: Live end-to-end with screen-control**

Start screen-control server (`/home/xeakaes/screen-control/start-server.sh`) with a valid API key in `config/secrets.json` (`screen_control_api_key`, mode 600). In CLI: set `screenshot` permission to `allow` in settings (or approve the ask prompt). Send: `Ekran görüntüsü al ve ekranda ne olduğunu kısaca söyle`. Expect: `tool_started(screenshot)` → `tool_finished(ok)` → second model call → final `assistant_message` describing the screen. If the server is down, expect `server_unreachable` fed to the model and a text-only graceful reply (spec §3.3).

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: bootstrap and CLI end-to-end"
```

---

## Done criteria (M0)

- `pytest tests` fully green.
- Live CLI: plain Ollama chat works; screenshot tool round-trip works; server-down path degrades gracefully.
- No Qt imports anywhere under `core/`.
- `config/secrets.json` is gitignored and mode 600.

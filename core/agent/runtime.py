"""Agent runtime: permissioned tool-calling loop (spec §3.1).

Flow: user text -> provider -> (text | tool calls) -> permission policy ->
tool execute -> result fed BACK to provider -> final text.

Cancellation contract (spec §3.5): tools receive a CancellationToken and
must check it before starting and between segments of long work. HTTP
`timeout=` bounds connection/read inactivity — it is not a hard
total-duration cap. Setting the token does not stop non-cancellable
in-flight work; this runtime only guarantees that a cancelled task stops
observing that work (late results discarded, no further model calls).
"""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

from core.agent.cancellation import CancellationToken, TaskCancelled
from core.agent.config import AgentConfig
from core.events import EventBus
from core.providers.base import ChatMessage, ModelProvider, ProviderError
from core.session.store import SessionStore
from core.tools.base import ToolResult
from core.tools.registry import PermissionLevel, PermissionPolicy, ToolRegistry


def _result_content(result: ToolResult) -> str:
    if result.ok:
        return json.dumps({"ok": True, "data": result.data or {}}, ensure_ascii=False)
    return json.dumps(
        {
            "ok": False,
            "error": result.error,
            "error_code": result.error_code,
        },
        ensure_ascii=False,
    )


class _Task:
    def __init__(self, task_id: str, session_id: str) -> None:
        self.task_id = task_id
        self.session_id = session_id
        self.token = CancellationToken()
        self.confirmations: dict[str, threading.Event] = {}
        self.confirm_approved: dict[str, bool] = {}
        self.confirm_lock = threading.Lock()


class AgentRuntime:
    def __init__(
        self,
        provider: ModelProvider,
        registry: ToolRegistry,
        policy: PermissionPolicy,
        events: EventBus,
        session: SessionStore,
        config: AgentConfig | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._policy = policy
        self._events = events
        self._session = session
        self._config = config or AgentConfig()
        self._tasks: dict[str, _Task] = {}
        self._active_task_id: str | None = None
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tool")

    @property
    def active_task_id(self) -> str | None:
        return self._active_task_id

    def begin_task(self, session_id: str, user_text: str) -> str:
        task_id = uuid.uuid4().hex
        task = _Task(task_id, session_id)
        self._tasks[task_id] = task
        self._active_task_id = task_id
        self._session.add_message(session_id, "user", user_text)
        return task_id

    def run_task(self, task_id: str) -> None:
        task = self._tasks[task_id]
        try:
            self._loop(task)
        finally:
            if self._active_task_id == task_id:
                self._active_task_id = None

    def start_task(self, session_id: str, user_text: str) -> str:
        task_id = self.begin_task(session_id, user_text)
        self.run_task(task_id)
        return task_id

    def cancel_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.token.cancel()
        with task.confirm_lock:
            for event in task.confirmations.values():
                event.set()
            task.confirmations.clear()

    def cancel_active_task(self) -> None:
        if self._active_task_id is not None:
            self.cancel_task(self._active_task_id)

    def resolve_confirmation(self, task_id: str, confirm_id: str, approved: bool) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        with task.confirm_lock:
            event = task.confirmations.pop(confirm_id, None)
            if event is None:
                return  # stale or double reply
            task.confirm_approved[confirm_id] = approved
            event.set()

    def _loop(self, task: _Task) -> None:
        sid, tid = task.session_id, task.task_id
        self._events.publish("agent_started", sid, tid, {})
        tool_calls_used = 0
        schemas = self._registry.schemas()
        if schemas and not self._provider.supports_tools:
            self._events.publish(
                "agent_error", sid, tid,
                {"error_code": "unsupported_capability", "message": "provider has no tool support"},
            )
            return
        try:
            while True:
                task.token.raise_if_cancelled()
                messages = self._session.messages(sid)
                try:
                    response = self._provider.complete(messages, schemas, task.token)
                except TaskCancelled:
                    raise
                except ProviderError as exc:
                    self._events.publish(
                        "agent_error", sid, tid,
                        {"error_code": exc.error_code, "message": exc.message},
                    )
                    return
                if not response.tool_calls:
                    text = response.text or ""
                    self._session.add_message(sid, "assistant", text)
                    self._events.publish("assistant_message", sid, tid, {"text": text})
                    self._events.publish("agent_finished", sid, tid, {"final_text": text})
                    return
                self._session.add_message(
                    sid, "assistant", response.text, tool_calls=response.tool_calls
                )
                for call in response.tool_calls:
                    task.token.raise_if_cancelled()
                    tool_calls_used += 1
                    if tool_calls_used > self._config.max_tool_calls:
                        self._events.publish(
                            "agent_error", sid, tid,
                            {"error_code": "max_tool_calls"},
                        )
                        return
                    result = self._run_one_tool(task, call.id, call.name, call.arguments)
                    if task.token.cancelled:
                        # late result discarded — never fed to the model
                        self._events.publish("agent_cancelled", sid, tid, {"reason": "cancelled"})
                        return
                    self._session.add_message(
                        sid, "tool", _result_content(result),
                        tool_call_id=call.id, name=call.name,
                    )
        except TaskCancelled:
            self._events.publish("agent_cancelled", sid, tid, {"reason": "cancelled"})

    def _run_one_tool(self, task: _Task, call_id: str, name: str, arguments: dict) -> ToolResult:
        sid, tid = task.session_id, task.task_id
        tool = self._registry.get(name)
        if tool is None:
            return ToolResult(
                ok=False,
                error=f"unknown tool: {name}",
                error_code="unknown_tool",
            )
        level = self._policy.check(name)
        if level is PermissionLevel.DENY:
            return ToolResult(
                ok=False,
                error="permission denied by policy",
                error_code="permission_denied",
            )
        if level is PermissionLevel.ASK:
            confirm_id = uuid.uuid4().hex
            event = threading.Event()
            with task.confirm_lock:
                # record BEFORE publish — synchronous subscribers must not race
                task.confirmations[confirm_id] = event
            self._events.publish(
                "confirmation_requested", sid, tid,
                {
                    "confirm_id": confirm_id,
                    "tool_name": name,
                    "question": f"Run tool {name}?",
                    "arguments": arguments,
                },
            )
            while True:
                if task.token.cancelled:
                    with task.confirm_lock:
                        task.confirmations.pop(confirm_id, None)
                    return ToolResult(
                        ok=False, error="cancelled while awaiting confirmation",
                        error_code="cancelled",
                    )
                if event.wait(0.05):
                    break
            with task.confirm_lock:
                approved = task.confirm_approved.pop(confirm_id, False)
            if not approved:
                return ToolResult(
                    ok=False, error="user denied permission",
                    error_code="permission_denied",
                )
        self._events.publish(
            "tool_started", sid, tid, {"tool_name": name, "arguments": arguments}
        )
        future = self._executor.submit(tool.execute, arguments, task.token)
        try:
            result = future.result(timeout=self._config.tool_timeout_s)
        except FuturesTimeout:
            future.cancel()
            result = ToolResult(
                ok=False, error="tool timed out", error_code="timeout"
            )
        except Exception as exc:  # tool crashed
            result = ToolResult(
                ok=False, error=str(exc), error_code="tool_exception"
            )
        self._events.publish(
            "tool_finished", sid, tid,
            {"tool_name": name, "ok": result.ok, "summary": result.error or "ok"},
        )
        return result

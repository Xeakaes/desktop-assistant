# Desktop AI Assistant — Design Spec

**Status:** Approved (design), pending implementation plan
**Date:** 2026-10-09
**Base infrastructure:** `computer-use-for-all-agents` (`/home/xeakaes/screen-control`)
**Roadmap source:** `Desktop_AI_Assistant_Long_Term_Roadmap.md` (Phase 1–2 + avatar addition)

---

## 1. Purpose

Build a desktop AI assistant whose primary interface is a floating 2D sprite
character on the desktop. The assistant talks to local/API models, can call
pluggable tools (first: screen-control), and reflects its internal state
(idle / thinking / working / speaking / error) through avatar animations.

`screen-control` is a **tool**, not a hard dependency: the app must work
without it; screen control is registered into a tool registry at runtime.

Guiding constraints from the roadmap:

- Infrastructure before product; assistant consumes tools, does not duplicate them.
- Modular: AI provider, computer-use backend, indexing, UI must each be replaceable.
- Safety by design: permissions checked on every tool call; model intent ≠ authorization.

---

## 2. Architecture overview

Two layers with a one-way dependency (`ui` → `core`, never reverse):

```
ui/ (PySide6)                     core/ (pure Python, no Qt)
┌─────────────────────┐          ┌──────────────────────────────┐
│ avatar window       │  events  │ Agent Runtime                │
│ chat bubble         │◄─────────│  ├─ ModelProvider (ollama,   │
│ settings window     │  commands│  │        openai_compat)      │
│ right-click menu    │─────────►│  ├─ ToolRegistry             │
└─────────────────────┘          │  │    └─ PermissionPolicy    │
                                 │  │         └─ screen_control │
                                 │  ├─ EventBus (callbacks)     │
                                 │  └─ SessionStore (in-memory) │
                                 └──────────────────────────────┘
                                              │ SDK (HTTP)
                                              ▼
                                 screen-control server :8745
```

### Project layout

```
desktop-assistant/
├── core/
│   ├── providers/
│   │   ├── base.py            # ModelProvider interface
│   │   ├── ollama.py          # local Ollama
│   │   └── openai_compat.py   # OpenAI-compatible APIs
│   ├── agent/
│   │   ├── runtime.py         # task loop, limits, cancellation
│   │   └── cancellation.py    # CancellationToken
│   ├── tools/
│   │   ├── base.py            # Tool, ToolResult
│   │   ├── registry.py        # ToolRegistry + PermissionPolicy
│   │   └── screen_control.py  # single concrete adapter (SDK)
│   ├── session/
│   │   └── store.py           # SessionStore (in-memory v1; SQLite later)
│   ├── events.py              # simple observer bus
│   └── config.py              # settings/secrets loading
├── ui/
│   ├── avatar/                # transparent window, sprite engine, state machine
│   ├── chat/                  # speech bubble panel
│   ├── settings/              # settings dialog
│   └── bridge.py              # EventBus → Qt signals
├── assets/avatars/base/       # default avatar: sprites + manifest.json
├── config/
│   ├── settings.json          # non-secret config (chmod 644)
│   └── secrets.json           # API keys, screen-control key (chmod 600)
├── tests/
│   ├── contract/              # fake provider/tool loop tests
│   ├── providers/
│   └── tools/
├── docs/
│   ├── specs/
│   └── plans/
└── requirements.txt
```

---

## 3. Core contracts

### 3.1 Agent flow (minimum contract)

```
User Message
     ↓
Agent Runtime  ── checks CancellationToken at every step
     ↓
Model Provider
     ↓
Model Response
     ├── normal text → assistant_message → UI
     └── tool call
            ↓
       PermissionPolicy.check(tool, args)   # every call, in code
            ├── deny  → tool result "permission denied" → back to model
            ├── ask   → confirmation_requested → UI → yes/no → model
            └── allow ↓
       ToolRegistry → Tool.execute(arguments, cancel)
            ↓
       tool_finished(result)
            ↓
       result fed BACK to Model Provider
            ↓
       final response → assistant_message → UI
```

Rules:

- Tool results are always returned to the model before any final answer.
- A model cannot authorize an action by merely requesting it; policy runs in code.

**Permission semantics (ask path made explicit):**

- Each confirmation request carries `(task_id, confirm_id, tool_name, question)`.
- The UI reply must match **both** `task_id` and `confirm_id`; a stale or
  mismatched reply is ignored.
- A denied call is **never executed**; the model receives a
  `permission_denied` tool result and may continue with an alternate plan.
- If the task is cancelled while a confirmation is pending, the pending
  request is invalidated (`confirm_id` expires) and no execution occurs,
  even if a late approval arrives.
- Model-provided tool arguments are never treated as authority — only the
  policy decision is.
- Defaults (configurable): max **10 tool calls per task**, **30 s per tool**,
  model-call timeout. Exceeding a limit ends the task with `agent_error`.

### 3.1b Model provider compatibility

`ollama.py` and `openai_compat.py` implement the same `ModelProvider`
interface, but tool-calling support is **not assumed to be identical** across
models:

- The provider layer **normalizes** tool calls into one internal form
  (tool name + arguments dict) regardless of wire format differences.
- A provider (or specific model) that lacks tool calling, tool results, or
  another needed feature **fails fast with an explicit capability error**
  (`error_code: "unsupported_capability"`) — never a silent text-only reply
  that pretends the tool ran.
- Malformed model output (invalid JSON arguments, unknown tool name) is
  handled safely: structured `invalid_arguments` / `unknown_tool` result fed
  back to the model once; repeated malformation ends the task with
  `agent_error` instead of looping.
- Provider capabilities are declared (`supports_tools`, etc.) so the UI can
  warn before a task starts.

### 3.2 Tool interface

```python
class Tool:
    name: str
    description: str
    input_schema: dict  # JSON Schema

    def execute(self, arguments: dict, cancel: CancellationToken) -> ToolResult
```

`ToolResult` is structured and uniform for success and failure:

```python
@dataclass
class ToolResult:
    ok: bool
    data: dict | None = None      # machine-readable payload on success
    error: str | None = None      # human-readable message on failure
    error_code: str | None = None # e.g. "timeout", "permission_denied",
                                  # "server_unreachable", "invalid_arguments"
```

Tools must poll `cancel` for long operations where possible; structured
`error_code` values keep model interpretation and test assertions stable.

### 3.3 screen_control adapter

- One concrete adapter; transport = existing Python SDK
  (`sdk/screen_control.py`, HTTP client to server on `127.0.0.1:8745`).
- Adapter exposes a small, stable tool set in v1: `screenshot`, `ocr_screen`,
  `mouse`, `keyboard`, `list_windows`, `focus_window` (subset; extend later).
- Agent never sees HTTP details, host, or API key.
- If the server is unreachable, the tool returns a structured error; the
  assistant continues without it (tool absence must not crash the app).

### 3.4 Events (EventBus)

Simple Python observer (list of callbacks), not a Qt copy and not a message
broker. Every event carries `(session_id, task_id, payload)` so multi-session
use will not mix events later.

| Event                 | Payload (minimum)                          |
|-----------------------|--------------------------------------------|
| `agent_started`       | user_text                                  |
| `assistant_message`   | text                                       |
| `tool_started`        | tool_name, arguments                       |
| `tool_finished`       | tool_name, ok, summary                     |
| `confirmation_requested` | tool_name, question, confirm_id         |
| `agent_error`         | message                                    |
| `agent_finished`      | final_text                                 |
| `agent_cancelled`     | reason                                     |

UI subscribes via `ui/bridge.py`, which re-emits as Qt signals using queued
connections (thread-safe delivery to the GUI thread).

### 3.5 Cancellation and shutdown

Cancellation is cooperative **and** bounded — a token alone does not stop a
blocked HTTP request or a runaway Qt worker:

- `CancellationToken` created per task; threaded through runtime and tools;
  tools poll it between steps.
- Every outbound call (model, screen-control SDK) sets an explicit **HTTP
  timeout**; timeouts surface as `error_code: "timeout"`, not hangs.
- The runtime checks the token between loop steps (before model call, before
  tool execute, before feeding results back).
- Long tools (e.g. screen-control with retries) split work into segments so
  the token is observed within the tool's own budget (≤ tool timeout).
- UI cancel button and app quit both call `token.cancel()`.
- On quit: cancel active task → bounded wait (≈2 s) → force-close remaining
  sockets/sessions → shutdown. Qt never relies on thread termination;
  workers finish or hit their timeout, then the loop exits.
- Cancellation mid-confirmation: pending `confirm_id` invalidated (see 3.1).

### 3.6 Session persistence

v1: in-memory `SessionStore` behind a small interface (list/add messages,
current task). SQLite persistence is a later drop-in; no UI-visible change.

### 3.7 Secrets

- `config/secrets.json` holds provider API keys and screen-control API key;
  file mode `0600`.
- Logs never include secrets, full tool arguments with keys, or auth headers.

---

## 4. UI design

### 4.1 Avatar

- Frameless, transparent, always-on-top PySide6 window; sprite animation via
  manifest-driven engine.
- **v1 states (5):** `idle`, `thinking`, `working`, `speaking`, `error`.
- State machine is driven **only** by core events (plus local UI events like
  bubble open). The animation system never drives the agent.
- `assets/avatars/<name>/manifest.json` maps state → frame list / fps / loop.
  Adding a character later = new folder; no agent code change. Future Live2D
  or AI-generated animation sets plug in at this layer only.

### 4.2 Chat bubble

- Opens above the character (toggle from right-click menu).
- Contains: recent transcript, text input, tool activity line, confirmation
  prompts (approve/deny), cancel button for the active task.

### 4.3 Right-click menu

- Ayarlar… / Sohbet / Karakter (config-level switch only in v1) / Çıkış.
- Menu and bubble share the same app-state machine.

### 4.4 Settings window

- Model provider: Ollama URL + model name; or API base URL + key + model.
- Screen-control connection: host, port, key (stored in secrets.json).
- Permission policy levels per tool (allow/ask/deny).
- Active avatar selection.

### 4.5 M0 CLI (temporary)

Until the UI lands, a small CLI (send line → print events incl. tool flow)
proves the core loop end-to-end. Deleted or kept as debug tool after M1.

---

## 5. Testing strategy

1. **Contract tests (core, headless, CI):** FakeProvider + FakeTool covering
   tool-call → result → final answer; permission deny; ask-denied path;
   stale/mismatched `confirm_id` ignored; cancel mid-loop; cancel while a
   confirmation is pending (late approval must not execute); malformed tool
   args; unknown tool name; max-call limit; provider without tool support
   fails fast (`unsupported_capability`).
2. **Provider tests:** Ollama / openai_compat against mocked HTTP.
3. **Adapter tests:** screen_control tool against a fake SDK client;
   real-server test optional/marked.
4. **UI smoke:** manifest loader + avatar state machine unit tests only;
   manual checklist for the real desktop (transparency, always-on-top,
   right-click, bubble, quit-while-busy).

---

## 6. Milestones

- **M0 — "Engine runs":** project skeleton, config, EventBus, tool interface,
  registry + policy, contract tests green, Ollama provider verified live,
  screen_control adapter, CLI end-to-end ("take a screenshot" → tool → model
  → final answer). No avatar yet. The M0 implementation plan must spell out
  concrete cancellation mechanics (HTTP timeouts, checkpoint placement,
  quit-while-busy sequence) per §3.5 — not just "use a token".
- **M1 — First face:** PySide6 avatar window (5 states), chat bubble,
  settings window, EventBus→Qt bridge.
- **M2 — Polished control:** right-click menu complete, confirmation prompts
  in bubble, safe quit while a task is running.
- **M3 — Persistence + extensibility:** SQLite session store; deepen
  renderer abstraction for future Live2D; additional tools (file index)
  as registry plugins.

Out of scope for v1 (deferred per roadmap): voice, wake word, file index,
PcHWmonitor, memory/personalization, AI-generated animation sets,
multi-window agent orchestration.

---

## 7. Open decisions (deferred, not blocking)

- Whether M3 keeps CLI as a debug front-end.
- Exact sprite art for `base` avatar (placeholder frames acceptable in M0/M1).
- Live2D evaluation criteria when the project reaches that maturity.

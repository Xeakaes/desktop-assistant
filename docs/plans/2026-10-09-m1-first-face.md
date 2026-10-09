# M1 — First Face (Avatar UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the assistant a face: a frameless transparent PySide6 avatar window animating 5 states from a generated Miku pixel-art sprite, with a chat bubble, a settings window, and an EventBus→Qt bridge.

**Architecture:** `core/` stays pure Python (no Qt, enforced by test). All new UI code lives in `ui/`. Sprite frames are pre-generated once by an offline script from the user's JPEG into `assets/avatars/base/` with a `manifest.json`; a pure-Python manifest loader and a pure-Python event→state reducer are unit-tested headlessly, and a thin Qt layer (bridge → sprite window → bubble → settings) renders them. The agent runs exactly as in M0 (`build_runtime` + `begin_task`/`run_task` on a worker thread); UI only consumes EventBus events.

**Tech Stack:** PySide6 (Qt widget UI), Pillow (offline asset generation only), pytest (headless unit tests), existing core (EventBus, AgentRuntime, build_runtime).

**Spec:** `docs/specs/2026-10-09-desktop-assistant-design.md` (§4.1 Avatar, §4.2 Chat bubble, §4.3 menu (minimal), §4.4 Settings, §5 test strategy item 4, §6 M1)

## Global Constraints

- `core/` must never import Qt/PySide6 (spec §2 architecture diagram; test enforces).
- Manifest states v1: exactly `idle`, `thinking`, `working`, `speaking`, `error` (spec §4.1).
- State machine is driven only by core events + local UI events; animation never drives the agent (spec §4.1).
- New character = new folder under `assets/avatars/`; no agent code change (spec §4.1).
- Secrets only ever in `config/secrets.json` mode `0600`, never logged (spec §3.6/§4.4).
- UI strings are Turkish (project convention).
- Unit tests: manifest loader + avatar state machine only; everything else is the manual desktop checklist (spec §5.4).
- All commands run from project root with `.venv/bin/`.

## Review Focus

1. **Unknown/renamed core event must not crash or change state** — EventBus may gain events later; reducer must return current state unchanged for unrecognized names. → `test_reduce_unknown_event_returns_current_state` (Task 3).
2. **Malformed manifest (missing state, empty frames, fps ≤ 0) must fail loudly at load, not freeze the window at runtime** — loader raises `ManifestError` naming the problem. → `test_manifest_missing_state_raises` / `test_manifest_empty_frames_raises` / `test_manifest_bad_fps_raises` (Task 2).
3. **`error` state must self-recover** — a stuck red avatar is unusable; reducer maps local event `error_timeout` → `idle`. → `test_error_timeout_returns_idle` (Task 3).
4. **Quit-while-busy must not hang or orphan the agent** — app quit calls `AgentRuntime.close()` (cancel + executor shutdown, already tested in M0); reducer maps `agent_cancelled` → `idle` so the face stops mid-task. → `test_agent_cancelled_returns_idle` (Task 3) + manual checklist item (Task 7).
5. **`core/` stays Qt-free** — one accidental `import PySide6` in core breaks the headless/CI story. → `test_core_has_no_qt_imports` (Task 4).

---

### Task 1: Sprite asset pipeline (offline script → committed frames + manifest)

**Files:**
- Create: `scripts/generate_avatar.py`
- Create: `assets/avatars/base/frames/*.png` (generated, committed)
- Create: `assets/avatars/base/manifest.json` (generated, committed)
- Source image: `/home/xeakaes/İndirilenler/Miku pixel art!.jpeg` (read-only input)

**Interfaces:**
- Consumes: none (offline one-shot script; Pillow only — installed in this task).
- Produces: `assets/avatars/base/manifest.json` schema that Task 2's loader consumes:

```json
{
  "name": "base",
  "states": {
    "idle":      {"frames": ["frames/idle_00.png", "..."], "fps": 6,  "loop": true},
    "thinking":  {"frames": ["frames/thinking_00.png", "..."], "fps": 4,  "loop": true},
    "working":   {"frames": ["frames/working_00.png", "..."], "fps": 10, "loop": true},
    "speaking":  {"frames": ["frames/speaking_00.png", "..."], "fps": 8,  "loop": true},
    "error":     {"frames": ["frames/error_00.png", "..."], "fps": 5,  "loop": false}
  }
}
```

- Command: `.venv/bin/python scripts/generate_avatar.py "/home/xeakaes/İndirilenler/Miku pixel art!.jpeg" --out assets/avatars/base`

- [ ] **Step 1: Install Pillow**

Run: `.venv/bin/pip install pillow` → expect success; then `git add requirements.txt` is not applicable (project has no requirements file — record versions with `pip freeze | grep -i pillow` in commit message body only).

- [ ] **Step 2: Write `scripts/generate_avatar.py`**

Pipeline (algorithm the implementer must follow — it is the design):
1. Load JPEG with Pillow, convert RGBA.
2. **Background removal:** flood-fill from all border pixels, replacing pixels within per-channel tolerance 48 of the seed color with transparent (kills graph paper + grid lines).
3. **Island removal:** among remaining opaque connected components, keep only the largest (drops the palette strip and the watermark); crop to its bbox; pad 8px transparent.
4. Resize to 192px height with `Image.NEAREST`, keep aspect.
5. Build `base` frame; derive state frames (integer-pixel transforms, never interpolated — pixel art stays crisp):
   - `idle` 4f: translateY `[0,-2,0,2]`, fps 6, loop
   - `thinking` 4f: translateX `[0,3,0,-3]`, fps 4, loop
   - `working` 6f: translateY `[0,-3,-5,-3,0,3]`, fps 10, loop
   - `speaking` 4f: translateY `[0,-4,0,-2]`, fps 8, loop
   - `error` 3f: red-tint overlay (40% red over non-transparent pixels), normal, red-tint — fps 5, **loop false**
6. Save every frame PNG + `manifest.json` exactly in the schema above.

- [ ] **Step 3: Run script and verify output**

Run: `.venv/bin/python scripts/generate_avatar.py "/home/xeakaes/İndirilenler/Miku pixel art!.jpeg" --out assets/avatars/base && ls assets/avatars/base/frames | wc -l && cat assets/avatars/base/manifest.json`
Expected: 21 frames (`idle`4 + `thinking`4 + `working`6 + `speaking`4 + `error`3 = 17 — count is 17, not 21), manifest parses, `python3 -c "import json; ..."` shows the 5 states. Spot-check one frame visually: `xdg-open assets/avatars/base/frames/idle_00.png` shows Miku on transparent (checkerboard) background, no grid/palette/watermark.

- [ ] **Step 4: Commit**

```bash
git add scripts/generate_avatar.py assets/
git commit -m "feat: generate base avatar sprite frames and manifest from Miku pixel art"
```

---

### Task 2: Manifest loader (pure Python)

**Files:**
- Create: `ui/avatar/__init__.py` (empty)
- Create: `ui/avatar/manifest.py`
- Test: `tests/ui/test_manifest.py`

**Interfaces:**
- Consumes: `assets/avatars/base/manifest.json` produced by Task 1.
- Produces:
  - `class ManifestError(ValueError)` — raised for any validation failure, message names the offending state/field.
  - `@dataclass(frozen=True) class StateAnim: frames: tuple[str, ...]; fps: float; loop: bool`
  - `def load_manifest(path: pathlib.Path) -> dict[str, StateAnim]` — keys are the 5 required state names; `frames` are absolute `Path`s resolved against the manifest's directory.

- [ ] **Step 1: Write failing tests**

`tests/ui/test_manifest.py`:

```python
from pathlib import Path
import pytest
from ui.avatar.manifest import ManifestError, load_manifest

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "avatars" / "base"
REQUIRED = {"idle", "thinking", "working", "speaking", "error"}

def test_real_manifest_loads():
    states = load_manifest(ASSETS / "manifest.json")
    assert set(states) == REQUIRED
    assert all(s.frames and s.fps > 0 for s in states.values())
    assert all((ASSETS / f).exists() for s in states.values() for f in s.frames)

def test_manifest_missing_state_raises(tmp_path):
    (tmp_path / "manifest.json").write_text('{"name":"x","states":{}}')
    with pytest.raises(ManifestError, match="missing state"):
        load_manifest(tmp_path / "manifest.json")

def test_manifest_empty_frames_raises(tmp_path):
    (tmp_path / "manifest.json").write_text(
        '{"name":"x","states":{"idle":{"frames":[],"fps":6,"loop":true},'
        '"thinking":{"frames":["f.png"],"fps":4,"loop":true},'
        '"working":{"frames":["f.png"],"fps":10,"loop":true},'
        '"speaking":{"frames":["f.png"],"fps":8,"loop":true},'
        '"error":{"frames":["f.png"],"fps":5,"loop":false}}}')
    with pytest.raises(ManifestError, match="frames"):
        load_manifest(tmp_path / "manifest.json")

def test_manifest_bad_fps_raises(tmp_path):
    # same 5-state JSON but idle fps = 0
    ...
    with pytest.raises(ManifestError, match="fps"):
        load_manifest(tmp_path / "manifest.json")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/ui/test_manifest.py -q` → expect FAIL (`ui.avatar` not found / import error).

- [ ] **Step 3: Implement `ui/avatar/manifest.py`**

`load_manifest` parses JSON, checks each of the 5 required states exists (else `ManifestError(f"missing state: {name}")`), frames non-empty (`ManifestError(f"state {name}: frames must be non-empty")`), fps > 0 (`ManifestError(f"state {name}: fps must be > 0")`), returns `dict[str, StateAnim]` with frames resolved to absolute paths (missing frame files are NOT checked here — only at window build time).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/ui/test_manifest.py -q` → expect 4 passed.

- [ ] **Step 5: Commit**

```bash
git add ui/avatar tests/ui/test_manifest.py
git commit -m "feat: manifest loader with validation for avatar states"
```

---

### Task 3: Avatar state machine (pure Python)

**Files:**
- Create: `ui/avatar/state_machine.py`
- Test: `tests/ui/test_state_machine.py`

**Interfaces:**
- Consumes: event names exactly as published by `core/events.py` (`agent_started`, `tool_started`, `tool_finished`, `assistant_message`, `agent_finished`, `agent_error`, `agent_cancelled`, `confirmation_requested`) plus local UI event `error_timeout`.
- Produces: `AvatarState = Literal["idle", "thinking", "working", "speaking", "error"]` and `def reduce_event(current: AvatarState, event_name: str) -> AvatarState` (pure, total function — never raises).

Transition table (single source of truth; spec §4.1 "driven only by core events"):

| event | → state |
|---|---|
| `agent_started` | `thinking` |
| `tool_started` | `working` |
| `tool_finished` | `working` |
| `confirmation_requested` | `working` |
| `assistant_message` | `speaking` |
| `agent_finished` | `idle` |
| `agent_cancelled` | `idle` |
| `agent_error` | `error` |
| `error_timeout` (local) | `idle` |
| anything else | unchanged |

- [ ] **Step 1: Write failing tests**

`tests/ui/test_state_machine.py`:

```python
from ui.avatar.state_machine import reduce_event

def test_each_event_maps_to_expected_state():
    cases = [
        ("idle", "agent_started", "thinking"),
        ("thinking", "tool_started", "working"),
        ("working", "tool_finished", "working"),
        ("working", "confirmation_requested", "working"),
        ("working", "assistant_message", "speaking"),
        ("speaking", "agent_finished", "idle"),
        ("working", "agent_cancelled", "idle"),
        ("idle", "agent_error", "error"),
        ("error", "error_timeout", "idle"),
    ]
    for cur, ev, want in cases:
        assert reduce_event(cur, ev) == want, (cur, ev)

def test_unknown_event_returns_current_state():
    assert reduce_event("thinking", "weird_new_event") == "thinking"
    assert reduce_event("error", "some_future_event") == "error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/ui/test_state_machine.py -q` → expect FAIL (module not found).

- [ ] **Step 3: Implement `ui/avatar/state_machine.py`**

Module-level `_TRANSITIONS: dict[str, AvatarState]` from the table; `reduce_event` returns `_TRANSITIONS.get(event_name, current)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/ui/test_state_machine.py -q` → expect 2 passed.

- [ ] **Step 5: Commit**

```bash
git add ui/avatar/state_machine.py tests/ui/test_state_machine.py
git commit -m "feat: pure avatar state machine driven by core events"
```

---

### Task 4: PySide6 setup, EventBus→Qt bridge, sprite window

**Files:**
- Create: `ui/__init__.py` (empty)
- Create: `ui/bridge.py`
- Create: `ui/avatar/window.py`
- Test: `tests/ui/test_qt_free_core.py`

**Interfaces:**
- Consumes: `core.events.EventBus.subscribe(name: str, cb)` (name `"*"` = all events), `Event` dataclass (`name`, `session_id`, `task_id`, `payload`); Task 2 `load_manifest`/`StateAnim`; Task 3 `reduce_event`.
- Produces:
  - `class QtBridge(QObject)` — `sig = pyqtSignal(object)`; `def __init__(self, bus: EventBus)` subscribes `"*"` and emits `sig` (thread-safe: Python worker threads emitting a Qt signal get queued delivery); consumers connect to `sig`.
  - `class AvatarWindow(QWidget)` — frameless, translucent, always-on-top; `def set_state(self, state: AvatarState) -> None`; `def current_state(self) -> AvatarState`; frames come from `load_manifest` at build time; `error` state plays once then falls back to rendering `idle` frame 0 (UI-local, mirrors `error_timeout`).
  - `def error_timeout_ms() -> int` returns `3000` (window starts its local `error_timeout` timer for this duration whenever it enters `error`).

- [ ] **Step 1: Install PySide6**

Run: `.venv/bin/pip install pyside6` → success.

- [ ] **Step 2: Write failing test**

`tests/ui/test_qt_free_core.py`:

```python
from pathlib import Path

def test_core_has_no_qt_imports():
    core = Path(__file__).resolve().parents[2] / "core"
    for f in core.rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        assert "PySide6" not in src and "PyQt" not in src, f"Qt leaked into {f}"
```

- [ ] **Step 3: Run test to verify it passes immediately**

Run: `.venv/bin/pytest tests/ui/test_qt_free_core.py -q` → expect PASS (guards a constraint, RED not expected; if it fails, someone already broke M0).

- [ ] **Step 4: Implement `ui/bridge.py` and `ui/avatar/window.py`**

`QtBridge`: on `sig`, consumers just call `reduce_event` themselves — bridge is transport only, no state.
`AvatarWindow`: `Qt.WA_TranslucentBackground`, `WindowFlags.FramelessWindowHint | WindowStaysOnTopHint | Tool`; a `QLabel` (or `QPixmap`-painting child) displays current frame scaled to 160px height; `QTimer` interval `1000/fps` advances frame index per `StateAnim`; `set_state` resets frame index, swaps timer interval; entering `error` starts a single-shot `QTimer(error_timeout_ms())` that emits local `error_timeout` handling by calling `set_state("idle")`.

- [ ] **Step 5: Offscreen smoke check (not a unit test)**

Run:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "
from pathlib import Path
from ui.avatar.manifest import load_manifest
from ui.avatar.window import AvatarWindow
import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
w = AvatarWindow(Path('assets/avatars/base'))
for s in ['idle','thinking','working','speaking','error']:
    w.set_state(s)
    assert w.current_state() == s
print('smoke ok', w.current_state())
"
```
Expected: `smoke ok error`.

- [ ] **Step 6: Commit**

```bash
git add ui/bridge.py ui/avatar/window.py ui/__init__.py tests/ui/test_qt_free_core.py
git commit -m "feat: Qt bridge and sprite avatar window with 5 states"
```

---

### Task 5: Chat bubble (§4.2 minus confirmation prompts — those are M2)

**Files:**
- Create: `ui/bubble.py`
- Test: none new (widget = manual checklist; spec §5.4) — but the *sending* path must reuse M0 runtime contracts already covered by contract tests.

**Interfaces:**
- Consumes: `QtBridge.sig` (tool activity line), callbacks passed in from `app.py`.
- Produces:

```python
class BubbleWindow(QWidget):
    def __init__(self, on_send: Callable[[str], None], on_cancel: Callable[[], None]) -> None
    def append_message(self, role: str, text: str) -> None   # role: "user" | "assistant" | "tool"
    def set_busy(self, busy: bool) -> None                    # enables/disables input, shows cancel
    def set_tool_activity(self, text: str) -> None            # one-line "▸ screenshot çalışıyor…" label
    def toggle(self) -> None
```

Layout: read-only `QPlainTextEdit` transcript, `QLabel` tool-activity line, `QHBoxLayout` with `QLineEdit` (placeholder `"Mesaj yazın…"`, Enter sends) + `QPushButton("Gönder")` + `QPushButton("İptal")` (visible/enabled only when busy). Frameless-ish styled panel (`QFrame` + objectName `"bubble"`), translucent, positioned above avatar by `app.py`.

- [ ] **Step 1: Implement `ui/bubble.py`**

Enter key and Gönder both call `on_send(text)` with non-empty stripped text, then clear the input; İptal calls `on_cancel()`. `append_message` prefixes user lines with `Sen:`, assistant with `Asistan:`, tool with `▸` and appends. Style via inline `QStyleSheet` (dark translucent panel, rounded corners) — no external .qss file (YAGNI for M1).

- [ ] **Step 2: Offscreen smoke check**

Run:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "
import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
sent = []
from ui.bubble import BubbleWindow
b = BubbleWindow(on_send=lambda t: sent.append(t), on_cancel=lambda: None)
b.append_message('user', 'merhaba'); b.append_message('assistant', 'selam')
b.set_tool_activity('▸ screenshot çalışıyor…'); b.set_busy(True); b.toggle()
assert 'merhaba' in b.findChild(__import__('PySide6.QtWidgets', fromlist=['QPlainTextEdit']).QPlainTextEdit).toPlainText()
print('bubble smoke ok')
"
```
Expected: `bubble smoke ok`.

- [ ] **Step 3: Commit**

```bash
git add ui/bubble.py
git commit -m "feat: chat bubble with transcript, input, tool activity line, cancel"
```

---

### Task 6: Settings window (§4.4)

**Files:**
- Create: `ui/settings.py`
- Test: none new (widget I/O is manual checklist; file-writing behavior verified by Step 3's round-trip script).

**Interfaces:**
- Consumes: `core.config.load_settings` / `load_secrets` file layout (existing `config/settings.json`, `config/secrets.json`).
- Produces:

```python
class SettingsWindow(QWidget):
    def __init__(self, settings_path: Path, secrets_path: Path) -> None
    def load(self) -> None    # populate fields from files
    def save(self) -> None    # write files back; secrets file stays mode 0600
```

Fields (form layout):
1. Provider: `type` combo (`ollama | openai_compat | nvidia | groq | google | nararouter`), `url`, `model` line edits.
2. Screen-control: `host`, `port`, `api_key` (password edit — value goes to secrets, never settings).
3. Permissions: one combo (`allow | ask | deny`) per known tool name + a `*` default combo; stored in `settings["permissions"]`.
4. Avatar: combo listing folder names under `assets/avatars/`; stored as `settings["avatar"]` (new key, default `"base"`).
5. Buttons: `Kaydet` (save + status label `"Kaydedildi"`), `Kapat`.

- [ ] **Step 1: Implement `ui/settings.py`**

`save()` for secrets: write JSON then `os.chmod(path, 0o600)` (mirrors `core.config.ensure_secrets_mode`). Never place `api_key` into `settings.json`.

- [ ] **Step 2: Round-trip verification (script, not unit test)**

Run:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "
import sys, json, copy, tempfile, pathlib, os
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from ui.settings import SettingsWindow
tmp = pathlib.Path(tempfile.mkdtemp())
sp, kp = tmp/'settings.json', tmp/'secrets.json'
sp.write_text(json.dumps({'provider':{'type':'groq','model':'qwen/qwen3.8-27b'},'permissions':{'*':'deny'}}))
kp.write_text(json.dumps({'groq_api_key':'x'}))
w = SettingsWindow(sp, kp); w.load()
w.save()
assert json.loads(kp.read_text())['groq_api_key'] == 'x'
assert oct(kp.stat().st_mode & 0o777) == '0o600'
print('settings round-trip ok')
"
```
Expected: `settings round-trip ok`.

- [ ] **Step 3: Commit**

```bash
git add ui/settings.py
git commit -m "feat: settings window for provider, screen-control, permissions, avatar"
```

---

### Task 7: App bootstrap: menu, wiring, headless verification, manual checklist

**Files:**
- Create: `ui/app.py`
- Create: `docs/checklists/m1-desktop-manual.md`
- Modify: `cli.py` — no change; M0 CLI stays as debug tool (spec §7 open decision).

**Interfaces:**
- Consumes: everything above + `core.bootstrap.build_runtime` (returns `(AgentRuntime, EventBus, SessionStore)`), `AgentRuntime.begin_task(session_id, text) -> str`, `run_task(task_id)` (blocking — must run on a worker `threading.Thread`), `cancel_active_task()`, `close()`, `SessionStore.messages(session_id)`.
- Produces: `def main() -> int` — entry point run as `.venv/bin/python -m ui.app`.

Wiring rules:
1. `build_runtime()`; `QtBridge(bus)`; `AvatarWindow(settings["avatar"] or "base")`.
2. Bridge `sig` handler (runs on GUI thread via queued connection): update bubble transcript from event payloads, `set_tool_activity` on `tool_started`/`tool_finished`, feed `reduce_event` → `avatar.set_state`, auto-open bubble on `agent_started`.
3. `on_send(text)`: append user message to bubble, `set_busy(True)`, spawn `threading.Thread(target=run_task_thread, daemon=True)` which does `tid = begin_task(sid, text); run_task(tid)` and finally `QMetaObject.invokeMethod`-style signal back to GUI (`set_busy(False)`) — implement via a small `pyqtSignal` on a QObject or `bridge.sig` reuse; never touch widgets from the worker thread.
4. Right-click menu (QMenu, Turkish): `Ayarlar…` → open/focus SettingsWindow; `Sohbet` → `bubble.toggle()`; `Karakter` → submenu of `assets/avatars/*` folders (writes `settings["avatar"]`, restart note in status); `Çıkış` → `runtime.close()` then `app.quit()`.
5. `aboutToQuit` → `runtime.close()` (covers quit-while-busy, Review Focus #4).

- [ ] **Step 1: Implement `ui/app.py`** with the wiring above.

- [ ] **Step 2: Offscreen full-boot smoke**

Run:
```bash
QT_QPA_PLATFORM=offscreen timeout 20 .venv/bin/python -c "
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
app = QApplication(sys.argv)
from ui.app import build_ui
ui = build_ui()            # constructs runtime, bridge, window, bubble, settings, menu — no exec loop
QTimer.singleShot(500, app.quit)
app.exec()
ui.close()
print('boot smoke ok')
"
```
Expected: `boot smoke ok`, exit 0, no tracebacks (agent not started — pure UI boot).

- [ ] **Step 3: Write manual checklist `docs/checklists/m1-desktop-manual.md`**

Items (each with checkbox): avatar visible top-right-ish, transparent background, always-on-top over other windows; idle bob animation runs ~6fps; send "ekran görüntüsü al" → thinking → working → speaking → idle; tool activity line updates; İptal stops task, avatar returns idle; right-click menu opens all 4 items; Ayarlar changes model and Kaydet persists; Sohbet toggle shows/hides bubble; avatar combo switches folder (after restart note); Çıkış during a running task exits cleanly ≤2s; error state (unplug network → send message) shows red flicker ~3s then recovers.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest tests -q` → expect all green (M0 73 + manifest 4 + state machine 2 + qt-free 1).

- [ ] **Step 5: Commit**

```bash
git add ui/app.py docs/checklists/m1-desktop-manual.md
git commit -m "feat: M1 app bootstrap with menu, wiring, and desktop checklist"
```

- [ ] **Step 6: Report to human partner**

Summarize: commands to launch (`.venv/bin/python -m ui.app`), which checklist items were verified by the human, deferred minors unaffected (they are core/CLI-only; no overlap with ui/).

---

## Self-review notes (resolved during writing)

- Frame count: 4+4+6+4+3 = 17 (corrected in Task 1 Step 3 expectation).
- Confirmation prompts deliberately excluded from bubble (spec §6: M2 owns them); bubble interface has no confirm hook.
- M0 CLI untouched (spec §7: M3 decides its fate).
- `settings["avatar"]` is a new key — SettingsWindow creates it with default `"base"`; AvatarWindow tolerates absence (`"base"` fallback).

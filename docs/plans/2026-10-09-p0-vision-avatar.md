# P0: Vision Support + Avatar Pack Location + Avatar Build Speed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the model actually see screenshots (vision), write custom avatar packs to a writable user directory, and stop the avatar build from freezing the UI.

**Architecture:** Three independent P0 fixes. Vision adds an `images` field to `ChatMessage` and threads base64 screenshot attachments through the tool-result → provider path, with a per-provider `supports_vision` flag and automatic OCR fallback. Avatar location moves custom packs from the read-only bundle `assets_dir()` to a writable `config_dir()/avatars`, with listing that merges bundle + user dirs. Avatar build pre-downscales the source image and runs `build_pack` on a `QThread`.

**Tech Stack:** Python 3.12, PySide6 (QThread), Pillow, requests, pytest.

**Spec:** Design approved in chat (2026-10-09). Vision wire format confirmed against Groq docs: `qwen/qwen3.8-27b` accepts `image_url` with `data:image/jpeg;base64,...` (max 3 images/request).

## Global Constraints

- `core/` must never import Qt (`tests/ui/test_qt_free_core.py` enforces this).
- All code, comments, commit messages in English; chat with user in Turkish.
- Default provider is `{"type": "groq", "model": "qwen/qwen3.8-27b"}` — confirmed vision-capable on Groq.
- Groq vision limits: max 3 images per request, 2048 tokens/image, 20MB request cap.
- Screenshot resize target: 1280px width, JPEG quality 85.
- Avatar build pre-downscale cap: 512px on the longest side.
- Custom packs live in `config_dir()/avatars`; bundle `base` stays read-only in `assets_dir()/avatars`.
- Test runner: `.venv/bin/pytest tests -q` with `QT_QPA_PLATFORM=offscreen` for UI tests.

## Review Focus

1. **Provider without vision** — if `supports_vision` is False, screenshot must fall back to OCR, never send a broken image payload (Task 1 test).
2. **Groq 3-image cap** — attaching more than 3 images must not blow the request; runtime should send only the most recent screenshot (Task 1).
3. **Ollama vs OpenAI wire format** — Ollama uses `images: [b64]` on the message, OpenAI-compat uses `content: [{type:image_url}]`; conflating them breaks one provider (Task 2 tests both).
4. **Bundle avatar never writable/deletable** — user pack delete and build must never touch `assets_dir()/avatars` (Task 3 test).
5. **QThread cleanup** — build thread must not leak or crash on window close; signals must be connected for combo refresh (Task 4).

---

### Task 1: Vision plumbing — ChatMessage.images, screenshot image, runtime OCR fallback

**Files:**
- Modify: `core/providers/base.py` (ChatMessage dataclass, ModelProvider.supports_vision)
- Modify: `core/tools/screen_control.py` (screenshot returns base64 image)
- Modify: `core/agent/runtime.py` (attach image to tool-result user message, OCR fallback)
- Modify: `core/config.py` (provider config gets supports_vision, or derive from provider type)
- Test: `tests/core/test_vision.py` (new)

**Interfaces:**
- Consumes: existing `ChatMessage`, `ToolResult`, `PermissionPolicy`, screenshot tool.
- Produces: `ChatMessage.images: list[str] | None` (data-URIs); `ModelProvider.supports_vision: bool`; screenshot `ToolResult.data` gains `"image": "data:image/jpeg;base64,..."`.

- [ ] **Step 1: Write failing tests for ChatMessage.images and screenshot image encoding**

```python
# tests/core/test_vision.py
from core.providers.base import ChatMessage
from core.tools.base import ToolResult

def test_chatmessage_images_default_none():
    m = ChatMessage(role="user", content="hi")
    assert m.images is None

def test_screenshot_tool_result_includes_data_uri(tmp_path, monkeypatch):
    from core.tools import screen_control
    # build a tiny real PNG via Pillow, stub client.screenshot to write it
    # assert result.data["image"] startswith "data:image/jpeg;base64," or "data:image/png;base64,"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/core/test_vision.py -v`
Expected: FAIL — `ChatMessage` has no `images` field / screenshot has no `image` key.

- [ ] **Step 3: Implement `images` field and screenshot encoding**

- `ChatMessage`: add `images: list[str] | None = None`.
- `ModelProvider`: add `supports_vision: bool = False`.
- `screen_control.py` screenshot: after `client.screenshot(output=path)`, load with Pillow, `img.thumbnail((1280, 1280))`, save as JPEG q=85 to a temp/in-memory buffer, base64-encode, return `{"path": path, "image": "data:image/jpeg;base64,<b64>"}`. Fall back to PNG data-URI if JPEG encode fails.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/core/test_vision.py -v`
Expected: PASS.

- [ ] **Step 5: Write failing test for runtime OCR fallback when provider lacks vision**

```python
def test_runtime_falls_back_to_ocr_without_vision(tmp_path):
    # provider.supports_tools=True, supports_vision=False
    # screenshot tool returns image; assert runtime invokes ocr_screen instead
    # OR asserts the image is stripped and a note is added
```

- [ ] **Step 6: Run test to verify it fails, then implement runtime fallback**

In `runtime.py`, when a vision-requiring tool (screenshot) result has an `image` but `not self._provider.supports_vision`: strip the image, log/emit a note, and (per design) fall back to `ocr_screen` for screen-reading tasks. Add the tool-result user message with `images` only when vision is supported and ≤3 images are attached (send most recent).

- [ ] **Step 7: Run full core test suite**

Run: `.venv/bin/pytest tests/core tests/test_runtime.py -q`
Expected: PASS, no regressions.

- [ ] **Step 8: Commit**

```bash
git add core/providers/base.py core/tools/screen_control.py core/agent/runtime.py core/config.py tests/core/test_vision.py
git commit -m "feat(vision): thread screenshot images to model with OCR fallback"
```

---

### Task 2: Provider wire formats — OpenAI-compat image_url + Ollama images

**Files:**
- Modify: `core/providers/openai_compat.py` (serialize_messages handles images, set supports_vision=True)
- Modify: `core/providers/ollama.py` (serialize_messages handles images, set supports_vision=True)
- Test: `tests/core/test_provider_vision.py` (new)

**Interfaces:**
- Consumes: `ChatMessage.images` from Task 1.
- Produces: OpenAI-compat messages use `content: [{type:"text"},{type:"image_url",image_url:{url:...}}]` when images present; Ollama messages use `images: [b64,...]`.

- [ ] **Step 1: Write failing OpenAI-compat serialize test**

```python
def test_openai_compat_serializes_images():
    from core.providers.openai_compat import serialize_messages
    from core.providers.base import ChatMessage
    msgs = [ChatMessage(role="user", content="look", images=["data:image/jpeg;base64,AAA"])]
    wire = serialize_messages(msgs)
    content = wire[0]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"] == "data:image/jpeg;base64,AAA"
```

- [ ] **Step 2: Write failing Ollama serialize test**

```python
def test_ollama_serializes_images():
    from core.providers.ollama import serialize_messages
    from core.providers.base import ChatMessage
    msgs = [ChatMessage(role="user", content="look", images=["data:image/jpeg;base64,AAA"])]
    wire = serialize_messages(msgs)
    assert wire[0]["images"] == ["data:image/jpeg;base64,AAA"]  # or strip data: prefix per Ollama spec
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/core/test_provider_vision.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement both serializers + set supports_vision=True on both providers**

- `serialize_messages` in each: if `m.images` present, emit the provider-specific image format; keep plain-string content when no images.
- Set `supports_vision = True` on `OpenAICompatProvider` and `OllamaProvider` (both wire formats handle images; other providers — google, etc. — stay False until implemented).
- Note: Ollama may expect raw base64 without the `data:` prefix — strip the prefix when building `images` list.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/core/test_provider_vision.py -v`
Expected: PASS.

- [ ] **Step 6: Run full suite + commit**

```bash
git add core/providers/openai_compat.py core/providers/ollama.py tests/core/test_provider_vision.py
git commit -m "feat(vision): serialize images for OpenAI-compat and Ollama providers"
```

---

### Task 3: Avatar pack location — writable user dir, merged listing

**Files:**
- Modify: `core/paths.py` (add `user_avatars_dir()`)
- Modify: `ui/settings.py` (`_list_avatars`, `_build_pack` target, `_delete_pack` scope)
- Modify: `ui/avatar_app.py` (`_make_avatar` lookup order)
- Test: `tests/ui/test_avatar_paths.py` (new)

**Interfaces:**
- Consumes: existing `assets_dir()`, `config_dir()`.
- Produces: `user_avatars_dir() -> Path` (= `config_dir()/avatars`, mkdir'd on demand).

- [ ] **Step 1: Write failing tests for user_avatars_dir + merged listing + build target**

```python
def test_user_avatars_dir_under_config(tmp_path, monkeypatch):
    monkeypatch.setattr("core.paths.config_dir", lambda: tmp_path)
    from core.paths import user_avatars_dir
    d = user_avatars_dir()
    assert d == tmp_path / "avatars"
    assert d.is_dir()  # created on demand

def test_list_avatars_merges_bundle_and_user(tmp_path, monkeypatch):
    # bundle has base; user has teto; list must include both, no dupes
```

- [ ] **Step 2: Run tests to verify they fail, then implement**

- `core/paths.py`: add `user_avatars_dir()` that returns `config_dir()/avatars` and `mkdir(parents=True, exist_ok=True)`.
- `ui/settings.py` `_list_avatars`: merge `assets_dir()/avatars` (bundle, read-only) + `user_avatars_dir()` (writable), dedupe, sort; `base` always present.
- `ui/settings.py` `_build_pack`: write to `user_avatars_dir()/name` instead of `assets_dir()/avatars`.
- `ui/settings.py` `_delete_pack`: only delete from `user_avatars_dir()`; never touch bundle.
- `ui/avatar_app.py` `_make_avatar`: check `user_avatars_dir()/name` first, then `assets_dir()/avatars/name`.

- [ ] **Step 3: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/ui/test_avatar_paths.py tests/ui/test_settings.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add core/paths.py ui/settings.py ui/avatar_app.py tests/ui/test_avatar_paths.py
git commit -m "fix(avatars): write custom packs to user config dir, merge bundle+user listing"
```

---

### Task 4: Avatar build speed + QThread

**Files:**
- Modify: `ui/avatar/pack.py` (pre-downscale to 512px before pipeline)
- Modify: `ui/settings.py` (QThread worker for build_pack)
- Test: `tests/ui/test_pack.py` (add thumbnail test), `tests/ui/test_settings.py` (threaded build test)

**Interfaces:**
- Consumes: `build_pack`, `user_avatars_dir()` from Task 3.
- Produces: build runs off the UI thread; combo refreshes via signal on completion.

- [ ] **Step 1: Write failing test for pre-downscale in pack.py**

```python
def test_build_pack_preserves_large_source(tmp_path):
    # create a 2000x2000 image, build_pack must succeed and produce 192px-tall frames
    # (implied: thumbnail happened before the slow pipeline)
```

- [ ] **Step 2: Run test to verify it fails, then implement pre-downscale**

In `build_pack`, after `img.load()`, before the pipeline: `img.thumbnail((512, 512))`. Keeps aspect, caps longest side at 512.

- [ ] **Step 3: Write failing test for threaded build in settings**

```python
def test_build_pack_runs_on_thread_and_refreshes(tmp_path, monkeypatch):
    # monkeypatch build_pack to a fast stub; assert _pack_build disabled during,
    # combo refreshed after, and no UI freeze (QThread used)
```

- [ ] **Step 4: Run test to verify it fails, then implement QThread worker**

Add a small `QThread`/`QObject` worker in `settings.py` that runs `build_pack`, emits success/failure signals, re-enables the button, refreshes the combo, and selects the new pack.

- [ ] **Step 5: Run full suite + commit**

```bash
git add ui/avatar/pack.py ui/settings.py tests/ui/test_pack.py tests/ui/test_settings.py
git commit -m "perf(avatars): pre-downscale source image and build pack on QThread"
```

---

### Task 5: Requirements + final verification

**Files:**
- Modify: `requirements.txt` (ensure Pillow present)
- Test: full suite

- [ ] **Step 1: Verify Pillow in requirements.txt**

If missing, add `Pillow>=10.0`.

- [ ] **Step 2: Run full test suite**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests -q`
Expected: all PASS (target ~180+).

- [ ] **Step 3: Manual smoke — launch `python -m ui.app`, take a screenshot task, confirm model responds about screen content.**

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: ensure Pillow in requirements"
```

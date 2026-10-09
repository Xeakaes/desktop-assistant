# Full GUI + Themes + History + Modes + i18n + Avatar Packs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver spec `docs/specs/2026-10-09-full-gui-and-avatar-packs-design.md`: Ollama-style chat GUI, collapsible sidebar, SQLite history, dark/light themes, first-run mode chooser with persistent preference and restart-based switching, complete tr/en i18n, and photo→avatar-pack generation in Settings.

**Architecture:** `core/` untouched (Qt-free test stays green). New pure modules first (`ui/i18n.py`, `ui/theme.py`, `ui/history.py`, `ui/mode.py`, `ui/avatar/pack.py`), then Qt layers on top (SettingsWindow v2, GUI MainWindow, mode dispatcher in `ui/app.py`). All UI strings go through a strict catalog; missing keys raise. Avatar M1 widgets adopt objectName QSS styling.

**Tech Stack:** PySide6 (existing), SQLite stdlib, Pillow (existing), pytest.

**Spec:** `docs/specs/2026-10-09-full-gui-and-avatar-packs-design.md`

## Global Constraints

- `core/` must never import Qt (existing test `tests/ui/test_qt_free_core.py`).
- i18n: languages exactly `("tr", "en")`; every catalog entry non-empty in both; missing key at runtime raises `MissingTranslationError` (spec §12).
- Mode/theme/lang persisted in `config/ui.json` only; secrets stay in `config/secrets.json` 0600.
- Mode switch = process restart via `os.execv` / `os._exit` (spec §3); no dual-window live mode.
- Custom avatar pack = same 5-state pipeline as Miku (`idle/thinking/working/speaking/error`), output `assets/avatars/<name>/` with `frames/` + `manifest.json` (spec §8).
- Turkish default language; UI strings via catalog only (spec §12).
- All commands from project root with `.venv/bin/`.
- M0 CLI (`cli.py`) and avatar mode keep working; full suite stays green.

## Review Focus

1. **i18n completeness gap** — a new UI string added without `tr`+`en` entries must fail tests, not ship mixed-language. → `test_every_key_has_both_languages` + `test_expected_keys_exist` (Task 1; extended in Task 6/7).
2. **History corruption / concurrent write** — two sessions writing from agent thread + UI thread; DB must not lose rows. → `test_append_from_multiple_threads_roundtrips` (Task 4).
3. **Mode config invalid values** — hand-edited `ui.json` with `"mode": "web"` or unreadable JSON must re-ask/default, never crash launch. → `test_load_ui_config_invalid_mode_returns_none` (Task 2).
4. **Theme token drift** — GUI objectNames styled in QSS but widget renamed → silent unstyled UI. → `test_qss_covers_required_objectnames` (Task 3) pins the objectName list.
5. **Pack name collision / bad image** — uploading `base` or a corrupt file must fail with a clear error and not destroy the existing `base` pack. → `test_build_pack_existing_dir_raises` + `test_build_pack_corrupt_image_raises` (Task 5).

---

### Task 1: i18n catalog (pure)

**Files:**
- Create: `ui/i18n.py`
- Test: `tests/ui/test_i18n.py`

**Interfaces:**
- Produces:
  - `LANGUAGES: tuple[str, ...] = ("tr", "en")`
  - `class MissingTranslationError(KeyError)`
  - `class I18n: def __init__(self, lang: str = "tr")`; `.current: str`; `.set_language(lang: str) -> None` (raises ValueError on unknown); `.t(key: str, **fmt) -> str` (strict lookup; formats via `str.format_map` when fmt non-empty)
  - Module singleton `i18n: I18n`
  - `STRINGS: dict[str, dict[str, str]]` — initial keys (at minimum): `app.title`, `mode.gui`, `mode.avatar`, `mode.choose_title`, `mode.choose_body`, `sidebar.new_chat`, `sidebar.sessions`, `sidebar.theme`, `sidebar.settings`, `sidebar.switch_avatar`, `sidebar.collapse`, `sidebar.expand`, `chat.input_placeholder`, `chat.send`, `chat.cancel`, `chat.tool_activity`, `chat.user_prefix`, `chat.assistant_prefix`, `chat.tool_prefix`, `chat.cancelled`, `chat.error_prefix`, `settings.title`, `settings.theme`, `settings.theme_dark`, `settings.theme_light`, `settings.mode`, `settings.lang`, `settings.lang_tr`, `settings.lang_en`, `settings.pack_title`, `settings.pack_pick`, `settings.pack_name`, `settings.pack_build`, `settings.pack_success`, `settings.pack_exists`, `settings.pack_bad_image`, `settings.save_restart_note`, `menu.settings`, `menu.chat`, `menu.avatar`, `menu.quit`, `menu.switch_gui`, `confirmation.pending`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from ui.i18n import I18n, LANGUAGES, MissingTranslationError, STRINGS, i18n

def test_languages_exact():
    assert LANGUAGES == ("tr", "en")

def test_every_key_has_both_languages():
    assert STRINGS
    for key, entry in STRINGS.items():
        assert set(entry) == set(LANGUAGES), key
        for lang in LANGUAGES:
            assert entry[lang].strip(), f"{key}/{lang} empty"

def test_expected_keys_exist():
    expected = ("app.title", "sidebar.new_chat", "settings.theme", "chat.send",
                "mode.choose_title", "menu.switch_gui", "settings.pack_build")
    for k in expected:
        assert k in STRINGS

def test_missing_key_raises():
    i = I18n("tr")
    with pytest.raises(MissingTranslationError):
        i.t("does.not.exist")

def test_language_switch_changes_output():
    i = I18n("tr")
    assert i.t("chat.send") == STRINGS["chat.send"]["tr"]
    i.set_language("en")
    assert i.t("chat.send") == STRINGS["chat.send"]["en"]

def test_format_placeholders():
    s = I18n("tr")
    STRINGS["__test_fmt"] = {"tr": "Merhaba {name}", "en": "Hello {name}"}
    try:
        assert s.t("__test_fmt", name="Ada") == "Merhaba Ada"
    finally:
        del STRINGS["__test_fmt"]

def test_unknown_language_raises():
    with pytest.raises(ValueError):
        I18n("fr")
```

- [ ] **Step 2: Run to verify FAIL**

Run: `.venv/bin/pytest tests/ui/test_i18n.py -q` → FAIL (module not found).

- [ ] **Step 3: Implement `ui/i18n.py`**

Strict catalog as specified; singleton `i18n = I18n("tr")`. Fill every key in `STRINGS` with natural Turkish and English strings (GUI-appropriate, concise).

- [ ] **Step 4: Run to verify PASS**

Run: `.venv/bin/pytest tests/ui/test_i18n.py -q` → expect 7 passed.

- [ ] **Step 5: Commit**

```bash
git add ui/i18n.py tests/ui/test_i18n.py
git commit -m "feat: i18n catalog and strict translator (tr/en)"
```

---

### Task 2: `config/ui.json` preferences (mode/theme/lang)

**Files:**
- Create: `ui/prefs.py`
- Test: `tests/ui/test_prefs.py`

**Interfaces:**
- Consumes: paths — `DEFAULT_UI_JSON = config/ui.json` resolved like `core.bootstrap.DEFAULT_SETTINGS`.
- Produces:
  - `@dataclass class UiPrefs: mode: str | None; theme: str; lang: str`
  - `def load_prefs(path: Path) -> UiPrefs` — mode None if absent/invalid; theme defaults `"dark"` if invalid; lang defaults `"tr"` if invalid; never raises on bad JSON (returns defaults).
  - `def save_prefs(path: Path, prefs: UiPrefs) -> None` — writes full object (creates parent dirs).
  - `def switch_mode(path: Path, mode: str) -> None` — validate `mode in ("gui", "avatar")` else ValueError; save; caller performs restart.

- [ ] **Step 1: Write failing tests** (missing file defaults; invalid mode→None; invalid theme/lang→defaults; roundtrip; switch_mode rejects "web").

- [ ] **Step 2: Run FAIL. Step 3: Implement `ui/prefs.py`. Step 4: Run PASS (expect 6).**

- [ ] **Step 5: Commit**

```bash
git add ui/prefs.py tests/ui/test_prefs.py
git commit -m "feat: ui.json prefs loader with validation defaults"
```

---

### Task 3: Theme QSS (pure)

**Files:**
- Create: `ui/theme.py`
- Test: `tests/ui/test_theme.py`

**Interfaces:**
- Produces:
  - `THEMES: dict[str, dict[str, str]]` for `"dark"` and `"light"` with tokens: `bg, bg_alt, fg, fg_muted, accent, accent_hover, border, bubble_user, bubble_assistant, danger`
  - `REQUIRED_OBJECTNAMES: tuple[str, ...] = ("main", "sidebar", "chat", "chat_input", "msg_user", "msg_assistant", "msg_tool", "bubble", "settings_win")`
  - `def qss(theme_name: str) -> str` — raises ValueError on unknown; output must contain `#name` for every entry in `REQUIRED_OBJECTNAMES` and every token value at least once for colors.

- [ ] **Step 1: Failing tests**

```python
def test_qss_unknown_raises(): ...
def test_qss_covers_required_objectnames():
    for name in ("dark", "light"):
        out = qss(name)
        for on in REQUIRED_OBJECTNAMES:
            assert f"#{on}" in out, (name, on)
def test_dark_and_light_differ():
    assert qss("dark") != qss("light")
```

- [ ] **Steps 2–4: RED → implement → GREEN (expect 3).**

- [ ] **Step 5: Commit** `"feat: dark/light theme token palettes and QSS builder"`

---

### Task 4: History store (SQLite, pure)

**Files:**
- Create: `ui/history.py`
- Test: `tests/ui/test_history.py`

**Interfaces:**
- Produces:
  - `def default_db_path() -> Path` — `~/.local/share/desktop-assistant/history.db` (or `%APPDATA%/desktop-assistant/history.db` on nt).
  - `class HistoryStore:`
    - `__init__(self, db_path: Path)` — mkdir parents, connect (`check_same_thread=False`), idempotent schema.
    - `create_session(title: str = "") -> str` (uuid4 hex; empty title → later renamed by first message)
    - `rename_session(session_id, title) -> None`
    - `list_sessions() -> list[tuple[str, str, float]]` newest first
    - `append(session_id, role, content, tool_name: str | None = None) -> None`
    - `messages(session_id) -> list[tuple[str, str, str | None]]`
    - `delete_session(session_id) -> None` (cascade)
    - `close() -> None`
  - Title auto-set: `append` of first `role=="user"` for a session with empty title → title = content[:40].

- [ ] **Step 1: Failing tests** — create/list order; append/messages roundtrip; auto-title 40 chars; delete cascade; `test_append_from_multiple_threads_roundtrips` (2 threads × 50 appends → 100 rows); second `HistoryStore` on same path reopens without error.
- [ ] **Steps 2–4: RED → implement (sqlite3, `threading.Lock` around writes) → GREEN (expect 7).**
- [ ] **Step 5: Commit** `"feat: SQLite history store for chat sessions"`

---

### Task 5: Avatar pack builder (refactor of generate_avatar)

**Files:**
- Create: `ui/avatar/pack.py`
- Modify: `scripts/generate_avatar.py` (thin CLI calling `build_pack`)
- Test: `tests/ui/test_pack.py`

**Interfaces:**
- Produces:
  - `class PackError(ValueError)`
  - `def sanitize_pack_name(name: str) -> str` — lowercase, `[a-z0-9_]`, strip edges, collapse `_`; empty → PackError.
  - `def build_pack(source_image: Path, out_dir: Path, name: str) -> Path` — runs the existing pipeline (move flood-fill / largest-component / crop / transforms from the script into this module); refuses if `out_dir` exists (`PackError("exists")`); writes `frames/` + `manifest.json` with the 5 states; returns `out_dir`.
  - Script keeps CLI: `python scripts/generate_avatar.py SRC --out DIR [--name N]` → calls `build_pack`.

- [ ] **Step 1: Failing tests** — use `/home/xeakaes/İndirilenler/Miku pixel art!.jpeg` into `tmp_path/"pack"` name `"miku"`: 5 states in manifest, frames exist; `build_pack(..., out_dir=existing)` raises PackError match exists; corrupt image (write `b"notimage"` to .jpg) raises PackError; `sanitize_pack_name("Miku Pixel Art!") == "miku_pixel_art"`.
- [ ] **Steps 2–4: RED → move code from script → GREEN (expect 4); re-run script CLI once to confirm `assets/avatars/base` regeneration still works (don't commit regenerated identical files unless changed).**
- [ ] **Step 5: Commit** `"feat: avatar pack builder extracted from generate_avatar"`

---

### Task 6: SettingsWindow v2 (theme, mode, lang, custom pack, retranslate)

**Files:**
- Modify: `ui/settings.py` (full rework of form; keep `merge_permissions`, `PROVIDER_KEY_SECRETS`, closeEvent-hide behavior)
- Test: extend `tests/ui/test_settings_merge.py`; new `tests/ui/test_settings_smoke.py` (offscreen)

**Interfaces:**
- Consumes: Task 1 `i18n`, Task 2 `load_prefs/save_prefs`, Task 5 `build_pack/sanitize_pack_name/PackError`, Task 3 theme names.
- Produces:
  - `class SettingsWindow(QWidget)` — same ctor `(settings_path, secrets_path, ui_json_path: Path | None = None, parent=None)`.
  - Sections top→bottom: **Genel** (Dil combo, Tema combo, Mod combo) → **Sağlayıcı** → **Ekran kontrolü** → **İzinler** → **Avatar** (existing combo + **Özel karakter** file pick + name + build button) → buttons Kaydet/Kapat.
  - `def retranslate(self) -> None` — re-setText every label/button/placeholder from `i18n.t`.
  - `save()` also writes `config/ui.json` theme/lang/mode via `save_prefs`.
  - Pack build: `QFileDialog.getOpenFileName` filter `Images (*.png *.jpg *.jpeg)`; on PackError show `i18n.t("settings.pack_bad_image")` or `pack_exists` in status; success → `pack_success` + refresh avatar combo.
  - `i18n.language_changed` (Qt signal bridge from Task 7, or direct call in tests) → `retranslate()`.

- [ ] **Step 1:** Unit: pack name sanitization integration (`build` button disabled until name+path set — smoke only). Offscreen smoke: construct with tmp paths; assert combos contain tr/en + dark/light + gui/avatar; trigger pack build with tmp image → directory created; retranslate after `set_language("en")` changes `windowTitle` to English.
- [ ] **Steps 2–4: RED → implement → GREEN (`pytest tests/ui -q` all green).**
- [ ] **Step 5: Commit** `"feat: settings v2 with theme, mode, language, custom avatar packs"`

---

### Task 7: GUI MainWindow + avatar retranslate wiring

**Files:**
- Create: `ui/gui/__init__.py`, `ui/gui/main_window.py`
- Modify: `ui/avatar/window.py` (drop inline `_STYLE`, objectName `bubble`/avatar labels; add `retranslate` no-op if no text), `ui/bubble.py` (objectName-based colors from theme; `retranslate` for placeholder/buttons)
- Test: `tests/ui/test_gui_smoke.py` (offscreen)

**Interfaces:**
- Consumes: Task 1–4 (i18n, prefs, theme, history), existing `build_runtime` + `QtBridge`.
- Produces:
  - `class MainWindow(QMainWindow)`:
    - ctor `(runtime, bus, session_store, history: HistoryStore, ui_json_path: Path, settings_path: Path, secrets_path: Path)`
    - Sidebar `QFrame` objectName `sidebar`: `+ Yeni sohbet` (`new_chat`), `QListWidget` sessions, buttons Tema (toggle dark/light, saves prefs), Ayarlar, Avatar'a geç (writes prefs mode=avatar + `os.execv` restart), ☰ collapse (260↔48, list hidden when collapsed).
    - Chat: `QScrollArea` objectName `chat` + `QVBoxLayout` of message frames (`msg_user`/`msg_assistant`/`msg_tool`); activity `QLabel`; input `QPlainTextEdit` objectName `chat_input` (Enter send, Shift+Enter newline); Gönder/İptal buttons.
    - `new_chat()`: `history.create_session()`; clear area; focus input.
    - `open_session(session_id)`: clear area; `history.messages` → render.
    - Send path mirrors M1 (`threading.Thread` + runtime); every user/assistant/tool event also `history.append`.
    - `retranslate()` walks registered widgets.
  - Module-level `language_bridge = QObject` with `language_changed = Signal()`; `i18n.set_language` callers emit it; MainWindow/Settings/Avatar subscribe.

- [ ] **Step 1: Offscreen smoke (no unit test for widgets per spec §10)** — construct MainWindow with temp HistoryStore + real runtime fakes or build_runtime; assert sidebar exists, sessions list length 0, collapse toggles width, send inserts user message frame + history row (use FakeProvider via build_runtime provider override if cheap; otherwise manual checklist covers live send).
- [ ] **Steps 2–4: implement → smoke PASS; full `pytest tests/ui -q` green.**
- [ ] **Step 5: Commit** `"feat: GUI main window with sidebar, chat, history browser"`

---

### Task 8: Mode dispatcher + first-run chooser + avatar switch item

**Files:**
- Modify: `ui/app.py` (main becomes dispatcher; existing avatar `App` moves to `ui/avatar_app.py` to keep files small)
- Create: `ui/gui/__init__.py` exports already done; `ui/chooser.py` (mode dialog)
- Test: extend `tests/ui/test_prefs.py` if needed; offscreen dispatcher smoke

**Interfaces:**
- Consumes: Task 2 `load_prefs/save_prefs`, Task 7 `MainWindow`, avatar App, `i18n`, theme apply.
- Produces:
  - `class ModeChooser(QDialog)` — two buttons (GUI/Avatar) using `i18n.t`; returns chosen mode; `exec()` then `save_prefs`.
  - `def main() -> int`: apply theme from prefs; if `prefs.mode is None` → chooser → save; `mode=="gui"` → MainWindow exec; else avatar App exec; both end with `os._exit`.
  - Avatar right-click menu gains `menu.switch_gui` item → `save_prefs(mode="gui")` + restart (same helper as GUI's switch button: `def restart_into(mode: str, ui_json: Path) -> None` in `ui/prefs.py` using `os.execv(sys.executable, [sys.executable, *sys.argv])` after save).

- [ ] **Step 1: Offscreen smoke** — with `ui.json` missing: chooser constructs; with `mode: gui`: `build_ui` path constructs MainWindow (no exec); with `mode: avatar`: constructs avatar App; `restart_into` writes file then (in test, monkeypatch os.execv) is called.
- [ ] **Steps 2–4: implement → PASS.**
- [ ] **Step 5: Commit** `"feat: mode dispatcher with first-run chooser and restart switching"`

---

### Task 9: Full-suite hardening + checklist + i18n audit

**Files:**
- Create: `docs/checklists/full-gui-desktop-manual.md`
- Modify: anything failing the suite

**Steps:**
- [ ] Step 1: `.venv/bin/pytest tests -q` — fix until green (expect M0+M1+new ≈ 110+).
- [ ] Step 2: Manual checklist file: both modes launch; first-run chooser persists; sidebar collapse; theme live toggle both modes; language live switch **zero** leftover foreign strings; history click restores; photo→pack→avatar list; quit-while-busy ≤2s; CLI still works.
- [ ] Step 3: Audit `STRINGS` keys vs UI call sites (`rg "i18n\.t\("` count vs catalog); add any missing keys (tests enforce both languages).
- [ ] Step 4: Commit `"feat: full GUI milestone checklist and i18n audit"`; ledger complete.

---

## Self-review notes (resolved while writing)

- Task 1 test uses `LANGUAGES` only (typo fixed here before execution).
- Avatar App moved to `ui/avatar_app.py` in Task 8 to keep dispatcher readable (plan deviation from "modify ui/app.py only" — recorded as ruling during execution if needed).
- Confirmation prompts remain M2 (activity-line placeholder `confirmation.pending` key only).
- `restart_into` uses `os.execv` on the same interpreter/argv; tests monkeypatch.

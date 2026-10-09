# Full GUI, Themes, History, Mode Switching & Custom Avatar Packs

**Date:** 2026-10-09
**Status:** approved design (brainstorming session)
**Extends:** `docs/specs/2026-10-09-desktop-assistant-design.md` (M0/M1 delivered)
**Out of scope (later milestones):** AI tool expansion (desktop automation deepening, file assistant, web search), packaging (exe/deb), GitHub repo publish (explicitly authorized by human partner at packaging time).

## 1. Intent

Grow the assistant from "avatar + bubble" into a full desktop AI application: an Ollama-style chat GUI as the primary surface, the existing avatar as a second mode, shared settings/theme infrastructure, persistent chat history, and a one-time mode preference. Users can also turn any character photo into a new avatar asset pack from Settings.

Success: one command (`python -m ui.app`) launches whichever mode was chosen; both modes share config, history, and settings; a new avatar pack from a photo appears in the avatar picker without restarting the agent code; dark and light themes both look coherent.

## 2. Decomposition (delivered in this milestone)

| Piece | What |
|---|---|
| A. GUI chat app | Main window, collapsible sidebar, chat area, theme toggle |
| B. Mode system | First-run chooser, persistent `mode` in `ui.json`, switch = process restart |
| C. History | SQLite session store, sidebar list, click-to-load transcript |
| D. Shared settings | One SettingsWindow used by GUI and avatar; adds Theme + Mode + Custom avatar pack sections |
| E. Theme | `ui/theme.py`, dark + light QSS, objectName-based styling |
| F. Custom avatar packs | Settings: pick photo → existing offline pipeline (`scripts/generate_avatar.py` logic, imported as a library) → `assets/avatars/<name>/` + selectable immediately |

Agent-tool expansion and packaging are explicitly **not** in this milestone (human partner decision: deliver source-only until the app matures; GitHub repo creation authorized only when packaging begins).

## 3. Mode system

- New file `config/ui.json`: `{"mode": "gui"|"avatar"|absent, "theme": "dark"|"light"}` (mode/theme absent → ask/default).
- Launch (`ui/app.py:main`): read `ui.json`. If `mode` missing → modal chooser (two big buttons: "Sohbet (GUI)" / "Avatar"); selection written to `ui.json`, then that mode starts. If present → start directly.
- Switch: GUI sidebar button "Avatar'a geç" and avatar right-click "Sohbet'e geç" both call `switch_mode("gui"|"avatar")` which writes `ui.json` and `os.execv` (process replace) — no dual-window live mode (human partner chose restart).
- `ui.json` lives next to `settings.json` under `config/`; not secret; mode/theme values validated on read (unknown → re-ask / default).

## 4. GUI layout (Ollama-style)

```
┌──────────┬──────────────────────────────┐
│ sidebar  │  chat area                   │
│ (260px,  │  (scrollable message list,   │
│ collapsi-│   tool activity line,        │
│ ble via  │   confirmation block M2*)    │
│ ☰)       │                              │
│          │  [input ................][➤] │
│ + Yeni   │  [İptal] when busy           │
│ sohbet   │                              │
│ sessions │                              │
│ ──────   │                              │
│ Tema     │                              │
│ Ayarlar  │                              │
│ Avatar'a │                              │
│ geç      │                              │
└──────────┴──────────────────────────────┘
```

- Sidebar collapse: ☰ toggles width 260 ↔ 48 (icons only).
- "Yeni sohbet": new session id, clears chat area.
- Session list from history store; title = first user message truncated to 40 chars.
- Chat area: bubbles as `QFrame`s in a `QVBoxLayout` inside `QScrollArea` (auto-scroll to bottom on new). Roles styled by objectName (`msg_user`, `msg_assistant`, `msg_tool`).
- Input: Enter sends, Shift+Enter newline (`QPlainTextEdit` single-height growing or `QLineEdit` — choose `QPlainTextEdit` max 4 lines).
- Tool activity line above input; İptal button enabled only while busy.
- Same agent wiring as M1: worker `threading.Thread` + `QtBridge`; events drive bubbles + activity; runtime never touched by GUI beyond `begin_task`/`run_task`/`cancel_active_task`/`close`.

Confirmation prompts (`ask` permission) remain **M2 follow-up** (unchanged from prior milestone): activity line shows "onay bekleniyor (M2)".

## 5. History (SQLite)

- New module `ui/history.py` (pure Python, no Qt).
- DB path: `Path.home() / ".local" / "share" / "desktop-assistant" / "history.db"` (Linux); same relative path under `%APPDATA%` when `os.name == "nt"` (future Windows readiness, not packaged yet).
- Schema:
  - `sessions(id TEXT PRIMARY KEY, title TEXT, created_at REAL)`
  - `messages(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, tool_name TEXT, ts REAL)`
- API:
  - `class HistoryStore: def __init__(self, db_path: Path)` — creates parent dirs, opens, migrates schema idempotently.
  - `def create_session(self, title: str = "") -> str` (uuid4 hex)
  - `def rename_session(self, session_id: str, title: str) -> None`
  - `def list_sessions(self) -> list[tuple[str, str, float]]` (id, title, created_at) newest first
  - `def append(self, session_id, role, content, tool_name: str | None = None) -> None`
  - `def messages(self, session_id) -> list[tuple[str, str, str | None]]` (role, content, tool_name)
  - `def delete_session(self, session_id) -> None` (cascade messages)
- GUI appends every user message, assistant message, and tool line on the corresponding events; session created on "Yeni sohbet" / first message with title = first user text.
- Avatar mode writes to the same store (same `HistoryStore` instance) but has no history browser yet (bubble transcript stays per-process; YAGNI).

## 6. Theme

- New module `ui/theme.py` (pure data + one Qt apply function).
- `THEMES: dict[str, dict[str, str]]` — token map per theme (`bg`, `bg_alt`, `fg`, `fg_muted`, `accent`, `accent_hover`, `border`, `bubble_user`, `bubble_assistant`, `danger`).
- `def qss(theme_name: str) -> str` — builds one stylesheet using tokens + objectNames (`#main`, `#sidebar`, `#chat`, `#msg_user`, `#msg_assistant`, `#msg_tool`, `#input`, `#bubble` (avatar), etc.). Pure string function, unit-tested.
- `def apply_theme(app: QApplication, theme_name: str) -> None` — `app.setStyleSheet(qss(theme_name))`.
- Avatar window/bubble drop inline stylesheets in favor of objectName styling so themes apply there too.
- Theme persisted in `config/ui.json`; Settings has a combo (Karanlık/Açık); toggle button in GUI sidebar flips and saves immediately; applied at startup.

## 7. Shared settings

- `SettingsWindow` (existing `ui/settings.py`) gains a top section:
  - **Tema:** combo Karanlık/Açık → writes `config/ui.json` `theme`.
  - **Mod:** combo Sohbet (GUI)/Avatar → writes `mode`; status text notes "değişiklik sonraki açılışta geçerli".
  - **Özel karakter:** line edit + "Fotoğraf seç…" button (file dialog, JPG/PNG); pack name line edit (default: file stem, sanitized `[a-z0-9_]`); "Paketi oluştur" button → runs the import pipeline (see §8); status label success/error; on success avatar combo refreshes.
- Existing provider/screen-control/permission/avatar sections unchanged (already shared).
- GUI sidebar "Ayarlar" opens the same class instance; avatar right-click "Ayarlar…" same.

## 8. Custom avatar packs

- `scripts/generate_avatar.py` refactors its core into importable `ui/avatar/pack.py`:
  - `def build_pack(source_image: Path, out_dir: Path, name: str) -> Path` — same pipeline as the Miku script (flood-fill bg removal, largest component, NEAREST resize, 5-state transforms, `manifest.json`); returns out_dir. Raises `PackError` (ValueError subclass) with a clear message on empty/corrupt images.
  - Script becomes a thin CLI wrapper; existing generated `base` pack untouched.
- Settings "Paketi oluştur" calls `build_pack` on the main thread with a 200ms wait-cursor (pack is ~1s for a 1MP photo; acceptable). Output: `assets/avatars/<name>/` with `frames/` + `manifest.json` (spinner optional — absent is fine).
- Name collisions: if `assets/avatars/<name>` exists → error "bu isim zaten var"; user picks another name. No overwrite.
- New pack immediately appears in Settings avatar combo, GUI avatar-mode restart note, and avatar-mode Karakter submenu (all read the directory listing live).
- Selected avatar continues to require app restart to take effect in avatar mode (existing behavior, status text already says so).

## 9. Entry point & wiring

- `ui/app.py:main` becomes mode dispatcher:
  1. Load `ui.json`; apply theme; ensure `HistoryStore` + runtime.
  2. If no mode → chooser dialog → save → continue.
  3. `mode == "gui"` → `ui/gui/main_window.py` exec loop; `mode == "avatar"` → existing App (avatar + bubble) exec loop.
- Both modes: `aboutToQuit` → `runtime.close()`; `os._exit` after exec (quit-while-busy behavior preserved).
- Avatar mode keeps right-click menu; replaces "Sohbet" bubble toggle item? Keep Sohbet (bubble) **and** add "Sohbet'e geç" (GUI mode). Bubble stays local transcript; GUI is the full app.

## 10. Testing

Unit (headless, pure):
- `ui/history.py`: create/list/rename/append/messages/delete; title truncation; DB path parent creation; idempotent init.
- `ui/theme.py`: `qss("dark")` and `qss("light")` contain every objectName used by GUI/avatar; both non-empty; unknown theme raises ValueError.
- `ui/avatar/pack.py`: `build_pack` on the existing Miku jpeg (tmp out) produces 5 states + frames exist; bad image raises PackError; name sanitization.
- `ui/mode.py` (if split): read/write/validate `ui.json`.

Offscreen smoke: GUI window constructs, sidebar collapses, theme applies, session list populates from a temp HistoryStore, mode chooser writes ui.json.

Manual desktop checklist: both modes launch, switch persists across restart, theme toggle live, photo→pack→select works, history click restores transcript, quit-while-busy still exits fast.

## 11. Constraints (carried)

- `core/` stays Qt-free (test).
- Secrets only in `config/secrets.json` 0600; never logged.
- Turkish UI strings (until i18n lands in §12 — then all strings go through the catalog).
- No network in tests; no GitHub publish; no packaging in this milestone.
- M0 CLI and avatar M1 behavior remain working (regression suite green).

## 12. Internationalization (i18n)

- Languages v1: **Türkçe (tr)** — default — and **English (en)**. Every user-visible string in both catalogs; no mixed-language screens (human partner requirement: switching a language must yield a complete UI — zero untranslated leftovers).
- Implementation: Qt `QTranslator` + `tr()` is **not** used (no `.ts` toolchain). Instead a small pure-Python catalog:
  - `ui/i18n.py` (pure, no Qt):
    - `LANGUAGES = ("tr", "en")`
    - `STRINGS: dict[str, dict[str, str]]` — flat key → {tr, en} map; keys are dotted English identifiers (`sidebar.new_chat`, `settings.theme`, `menu.avatar_mode`, …).
    - `class I18n: def __init__(self, lang: str)`; `def t(self, key: str, **fmt) -> str` — lookup, `KeyError` → raises `MissingTranslationError` (so missing keys fail tests, not ship silently); `**fmt` applied via `str.format_map` when placeholders present.
    - `def set_language(self, lang: str) -> None`; `current` property.
  - Module-level singleton `i18n = I18n("tr")` imported as `from ui.i18n import i18n`.
- All UI construction sites call `i18n.t("...")`; dynamic labels re-render on language change via a `language_changed` signal on a small `QObject` notifier (`ui/i18n_bridge.py`) **or** full window rebuild — choose rebuild-on-change for simplicity (Settings saves language → status "dil değişikliği yeniden başlatmada geçerli" is **not** accepted: language applies immediately in the open window by re-translating all registered widgets).
  - Simplest reliable approach: `MainWindow`/`SettingsWindow`/`AvatarWindow` register their translatable widgets via `retranslate()` methods that re-`setText`/`setPlaceholderText` from catalog; `i18n.language_changed` signal calls each registered `retranslate`.
- Language persisted in `config/ui.json` as `"lang": "tr"|"en"`.
- Settings gains "Dil" combo (Türkçe/English); change applies immediately (no restart).
- First-run mode chooser is translated too (catalog keys).
- Completeness test (unit): `test_every_key_has_both_languages` — every entry in `STRINGS` has non-empty `tr` and `en`; plus a registry test that walks a frozen list of expected keys used by GUI+avatar (explicit `EXPECTED_KEYS` tuple in the test) asserting no orphan/missing keys. Adding a UI string without catalog entries fails CI.
- Runtime safety: `MissingTranslationError` in dev/tests; in the shipped UI path `t()` is still strict (fail loud beats half-translated UI; catalog completeness is enforced by tests).

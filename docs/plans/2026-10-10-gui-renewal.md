# GUI Renewal and Chat Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Radically renew the GUI visual design (near-black dark / soft pastel light, Nunito, coral accent) and add right-click chat-history deletion with confirmation.

**Architecture:** All visual values live in `ui/theme.py` (palette tokens + one QSS builder). The renewal replaces the palette, extends the QSS with focus rings, scrollbar, tab, pill and outline-button rules, bundles the Nunito font, restructures Settings into tabs, and adds a delete-session flow in `ChatWindow` backed by the existing `HistoryStore.delete_session`. `core/` is untouched.

**Tech Stack:** PySide6, QSS (no transitions — Qt limitation), QFontDatabase, Pillow-free.

**Spec:** `docs/specs/2026-10-10-gui-renewal-design.md` (v2, user-approved). The plan argues from the spec; executors read both.

## Global Constraints

- `core/` must not import Qt; this plan touches `ui/` and `assets/` only.
- `REQUIRED_OBJECTNAMES` contract in `ui/theme.py` stays valid; every new objectName styled by QSS is added to the tuple and the contract test.
- i18n: every new user-facing string is in `ui/i18n.py` with both `tr` and `en` (fail-loud catalog).
- All existing tests (191 at plan time) stay green after every task; full suite: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests -q`.
- TDD: write the failing test first, run it, implement, run again, commit.
- Exact token values are pinned in the spec §4.1; do not invent colors, radii (14px cards / 10px controls / 999px pills) or spacing (4/8/12/16/24/32).
- Destructive controls are filled danger (`color: on_danger`); cancel/neutral controls use `#outline` (2px `input_border`, transparent fill); outline-danger next to accent fills is forbidden.
- No QSS transitions; focus ring = persistent 2px border that swaps color on `:focus` (no size jump).

## Review Focus

Failure modes the spec implies that are most likely to bite a user; each is pinned to the task that owns the code:

1. **Deleting the active session while a task is running** — the task must be cancelled first, and the late `agent_cancelled` signal must not append to (or crash on) the deleted session. Pinned in Task 5 (`test_delete_active_while_running_no_late_append`).
2. **After a delete, the next send must create a fresh session id**, never resurrect the deleted one. Pinned in Task 5 (`test_send_after_delete_creates_new_session`).
3. **Focus rings must not resize widgets** — every focusable selector carries a 2px border in its normal state. Pinned in Task 1 (`test_focus_rules_reserve_two_pixel_border`).
4. **WCAG AA pairs are pinned, not aspirational** — light `#FFFFFF` on `#D1433B`, dark `#1A0E0E` on `#F87171`; token parity dark↔light. Pinned in Task 1 (`test_accent_contrast_pairs_pinned`, `test_themes_have_identical_token_keys`).
5. **Nunito must actually load** (id != -1) and a missing file must degrade gracefully (return -1, app still starts). Pinned in Task 2 (`test_load_fonts_adds_application_font`, `test_load_fonts_missing_file_returns_minus_one`).

---

### Task 1: Theme tokens and QSS rebuild

**Files:**
- Modify: `ui/theme.py` (whole file: THEMES, REQUIRED_OBJECTNAMES, qss())
- Test: `tests/ui/test_theme.py` (extend)

**Interfaces:**
- Consumes: nothing (foundation task).
- Produces: `THEMES` with token set {bg, bg_alt, surface, surface_hover, border, input_border, fg, fg_muted, accent, accent_hover, bubble_user, bubble_assistant, danger, on_accent, on_danger} for both themes; `REQUIRED_OBJECTNAMES` extended with `new_chat`, `sessions_header`, `empty_state`, `outline`; `qss(theme_name) -> str` covering the contract plus focus/scrollbar/tab/menu rules. Later tasks style widgets by objectName only.

- [ ] **Step 1: Write the failing tests**

Extend `tests/ui/test_theme.py`:

```python
def test_themes_have_identical_token_keys():
    assert set(THEMES["dark"]) == set(THEMES["light"])
    expected = {
        "bg", "bg_alt", "surface", "surface_hover", "border", "input_border",
        "fg", "fg_muted", "accent", "accent_hover", "bubble_user",
        "bubble_assistant", "danger", "on_accent", "on_danger",
    }
    assert set(THEMES["dark"]) == expected


def test_accent_contrast_pairs_pinned():
    # Spec §4.1 / §6: AA-passing pairs computed in the design review.
    assert THEMES["light"]["accent"] == "#D1433B"
    assert THEMES["light"]["on_accent"] == "#FFFFFF"
    assert THEMES["light"]["accent_hover"] == "#B93530"
    assert THEMES["dark"]["accent"] == "#F87171"
    assert THEMES["dark"]["on_accent"] == "#1A0E0E"
    assert THEMES["dark"]["bg"] == "#0D0D0D"
    assert THEMES["dark"]["border"] == "#2E2E2E"
    assert THEMES["dark"]["input_border"] == "#5C5C62"
    assert THEMES["light"]["input_border"] == "#8E8E93"


def test_focus_rules_reserve_two_pixel_border():
    for name in ("dark", "light"):
        style = qss(name)
        # Focusable selectors keep a 2px border in the normal state so the
        # :focus color swap cannot change layout size (spec §4.4).
        assert "border: 2px" in style
        assert ":focus" in style


def test_qss_has_scrollbar_tabs_and_outline():
    style = qss("dark")
    assert "QScrollBar" in style
    assert "QTabWidget" in style
    assert "QPushButton#outline" in style
    assert "QFrame#empty_state" in style
    assert "QLabel#sessions_header" in style
    assert "QPushButton#new_chat" in style
```

The existing `test_qss_covers_required_objectnames` stays; it will fail until the contract tuple and QSS selectors are updated in Step 3.

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ui/test_theme.py -v`
Expected: FAIL — new token keys missing, `#D1433B` not found, `QScrollBar` not in QSS.

- [ ] **Step 3: Rewrite `ui/theme.py`**

- Replace both `THEMES` dicts with the spec §4.1 tables verbatim (all 15 tokens per theme).
- Extend `REQUIRED_OBJECTNAMES` with `("new_chat", "sessions_header", "empty_state", "outline")`.
- Rewrite `qss()` keeping every existing selector and adding:
  - `QPushButton#new_chat` — accent fill, `border-radius: 14px` (pill), `on_accent` text.
  - `QLabel#sessions_header` — `fg_muted`, bold, 12px top margin feel via padding.
  - `QListWidget::item` — padding 8px, `border-radius: 10px`; `:hover` → `surface_hover`; `:selected` → accent fill + `on_accent` text.
  - `QFrame#empty_state` — transparent; inner labels: title `fg`, hint `fg_muted`.
  - `QPushButton#outline` — transparent fill, `border: 2px solid input_border`, `fg` text; `:hover` → `surface_hover` background; `:focus` → border color `accent`.
  - Global `QPushButton` — keep accent fill; give it `border: 2px solid accent` (reserved focus ring) with `:focus { border-color: accent_hover }`.
  - `QPlainTextEdit#chat_input`, `QLineEdit`, `QComboBox` — `border: 2px solid input_border`, `:focus { border-color: accent }`, radius 10px.
  - `QPushButton#danger` — `background: danger; color: on_danger; border: 2px solid danger`.
  - `QScrollBar:vertical` — width 8px, transparent background, handle `surface_hover` with `border-radius: 4px`, `:hover` handle → `input_border`; horizontal analog.
  - `QTabWidget::pane` — `border: 1px solid border`, top margin 8px; `QTabBar::tab` — padding 8px 16px, `bg_alt`, `fg_muted`, top corners 8px; `:selected` → `bg` background + `accent` text.
  - `QMenu` — radius 10px, padding 4px; keep `::item:selected` accent fill with `on_accent`.
  - `QListWidget` container — border `border`, radius 10px (existing rule updated).
  - `QFrame#msg_user/assistant` — radius 14px (up from 10px); `msg_tool` radius 10px, background `surface_hover`.
  - `QFrame#bubble` — radius 14px; inner controls radius 10px with `input_border`.
  - `QWidget#settings_win`, `QLabel#muted`, disabled buttons: keep semantics, swap to new token values.
- Values only from `THEMES`; spacing from the 4/8/12/16/24/32 scale.

- [ ] **Step 4: Run full theme tests and the whole suite**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ui/test_theme.py -q && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests -q`
Expected: theme tests PASS; full suite PASS (other UI tests assert behavior, not colors).

- [ ] **Step 5: Commit**

```bash
git add ui/theme.py tests/ui/test_theme.py
git commit -m "feat(theme): pastel/near-black palette, focus rings, scrollbar, tabs, outline button"
```

---

### Task 2: Bundle and load Nunito

**Files:**
- Create: `assets/fonts/Nunito.ttf`
- Create: `ui/fonts.py`
- Modify: `ui/app.py:27-33` (main(), after QApplication creation)
- Modify: `ui/avatar_app.py` (main(), after QApplication creation)
- Test: `tests/ui/test_fonts.py` (new)

**Interfaces:**
- Consumes: nothing.
- Produces: `load_fonts(app) -> int` in `ui/fonts.py` — returns the QFontDatabase font id, or `-1` when the file is missing or fails to load. Never raises. Called once per process from both entry points.

- [ ] **Step 1: Download the font**

```bash
mkdir -p assets/fonts
curl -L -o assets/fonts/Nunito.ttf \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/nunito/Nunito%5Bwght%5D.ttf"
ls -la assets/fonts/Nunito.ttf
```

Verify: file size > 100 KB. If the variable-font URL fails, fall back to the static Regular instance from the same repo path (`Nunito-Regular.ttf` renamed to `Nunito.ttf`) and note it in the commit message. The font is OFL-licensed (spec §4.2).

- [ ] **Step 2: Write the failing tests**

`tests/ui/test_fonts.py`:

```python
from pathlib import Path


def test_nunito_bundled():
    assert Path("assets/fonts/Nunito.ttf").is_file()
    assert Path("assets/fonts/Nunito.ttf").stat().st_size > 100_000


def test_load_fonts_adds_application_font():
    from PySide6.QtWidgets import QApplication

    from ui.fonts import load_fonts

    app = QApplication.instance() or QApplication([])
    font_id = load_fonts(app)
    assert font_id != -1


def test_load_fonts_missing_file_returns_minus_one(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    import ui.fonts

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui.fonts, "FONT_PATH", tmp_path / "nope.ttf")
    assert ui.fonts.load_fonts(app) == -1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ui/test_fonts.py -v`
Expected: FAIL — `ui.fonts` not importable.

- [ ] **Step 4: Implement `ui/fonts.py` and wire the entry points**

`ui/fonts.py`:

```python
"""Bundled UI font loading (spec §4.2)."""
from pathlib import Path

FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Nunito.ttf"


def load_fonts(app) -> int:
    """Load the bundled Nunito font; return the font id or -1 (never raises)."""
    ...
```

Implementation: if `FONT_PATH` is missing → return -1; else `QFontDatabase.addApplicationFont(str(FONT_PATH))`. Add the same call `load_fonts(app)` immediately after `QApplication(...)` in `ui/app.py:main()` and `ui/avatar_app.py:main()`. No other font plumbing yet — Task 3's QSS already says `font-family: Nunito`.

- [ ] **Step 5: Run tests and the whole suite**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ui/test_fonts.py -q && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add assets/fonts/Nunito.ttf ui/fonts.py ui/app.py ui/avatar_app.py tests/ui/test_fonts.py
git commit -m "feat(fonts): bundle Nunito (OFL) and load via QFontDatabase at startup"
```

---

### Task 3: Main window visual renewal

**Files:**
- Modify: `ui/gui/main_window.py` (sidebar construction, empty state, cancel button objectName, retranslate)
- Modify: `ui/i18n.py` (two new keys)
- Modify: `ui/theme.py` (`qss()` adds `font-family: Nunito` on `QWidget#main`)
- Test: `tests/ui/test_chat.py` (extend)

**Interfaces:**
- Consumes: `THEMES`/`qss()` objectNames from Task 1 (`new_chat`, `sessions_header`, `empty_state`, `outline`); `sidebar.sessions` i18n key (already exists, orphaned).
- Produces: `ChatWindow._empty_state: QFrame`, `ChatWindow._sessions_header: QLabel`; cancel button objectName becomes `"outline"`. Deletion Task 5 reuses `_clear_messages()`'s empty-state restore.

- [ ] **Step 1: Add i18n keys**

In `ui/i18n.py` STRINGS, next to the other `chat.*` keys:

```python
"chat.empty_title": {"tr": "Merhaba! Bir sohbet başlat.", "en": "Hi! Start a chat."},
"chat.empty_hint": {
    "tr": "Asistana ne sormak istersiniz?",
    "en": "What would you like to ask?",
},
```

- [ ] **Step 2: Write the failing tests**

Extend `tests/ui/test_chat.py`:

```python
def test_sidebar_has_sessions_header(tmp_path):
    app, win = _make_window(tmp_path)
    assert win._sessions_header.objectName() == "sessions_header"
    assert win._sessions_header.text() == "Geçmiş sohbetler"  # i18n default tr
    win.hide()


def test_empty_state_visible_when_no_messages_then_hides(tmp_path):
    app, win = _make_window(tmp_path)
    win._runtime = FakeRuntime(win)
    assert not win._empty_state.isHidden()
    win._chat_input.setPlainText("selam")
    win._send()
    assert win._empty_state.isHidden()
    win.new_chat()
    assert not win._empty_state.isHidden()
    win.hide()


def test_cancel_button_uses_outline_not_danger(tmp_path):
    app, win = _make_window(tmp_path)
    assert win._cancel_btn.objectName() == "outline"
    win.hide()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ui/test_chat.py -v -k "sidebar_has or empty_state or outline"`
Expected: AttributeError / assertion failures.

- [ ] **Step 4: Implement**

In `ChatWindow.__init__` (`ui/gui/main_window.py`):
- Create `self._sessions_header = QLabel(self)` with `setObjectName("sessions_header")`; insert above `self._sessions` in `side_layout`.
- Give `self._new_chat_btn` `setObjectName("new_chat")`.
- Change `self._cancel_btn.setObjectName("danger")` → `setObjectName("outline")`.
- Create `self._empty_state = QFrame(self)` with `setObjectName("empty_state")`, a `QVBoxLayout` of two center-aligned QLabels (title `chat.empty_title`, hint `chat.empty_hint`, hint objectName `muted`); insert at index 0 of `self._msg_layout` so it sits above the stretch.
- In `_append()`: `self._empty_state.hide()` before inserting the message frame.
- In `_clear_messages()`: after clearing, `self._empty_state.show()`.
- In `retranslate()`: set `self._sessions_header.setText(i18n.t("sidebar.sessions"))` and the two empty-state label texts.
- In `ui/theme.py` `qss()`: add `font-family: Nunito, sans-serif;` to the `QWidget#main` rule (and `QWidget#settings_win` / `QFrame#bubble` roots for consistency).

Check `tests/ui/test_chat.py` for any assertion on the cancel button's old `danger` objectName or on `_cancel` styling and update it to `outline` (behavior unchanged).

- [ ] **Step 5: Run tests and the whole suite**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ui/test_chat.py -q && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests -q`
Expected: PASS (fix any collateral test that referenced the old objectName).

- [ ] **Step 6: Commit**

```bash
git add ui/gui/main_window.py ui/i18n.py ui/theme.py tests/ui/test_chat.py
git commit -m "feat(gui): sidebar header, pill new-chat, empty state, neutral outline cancel"
```

---

### Task 4: Settings window tabs

**Files:**
- Modify: `ui/settings.py:200-200` (the QVBoxLayout build in `__init__`)
- Test: `tests/ui/test_settings.py` (extend)

**Interfaces:**
- Consumes: existing `settings.section_*` i18n keys (`i18n.py:72-76`); existing widget attributes (`self._lang`, `self._theme`, `self._provider_type`, …) — **all attribute names must stay unchanged** so existing load/save tests pass untouched.
- Produces: a `QTabWidget` with five titled tabs; `_status` and the save/close row remain below the tab widget.

- [ ] **Step 1: Write the failing test**

Extend `tests/ui/test_settings.py`:

```python
def test_settings_has_five_titled_tabs(tmp_path):
    from PySide6.QtWidgets import QApplication, QTabWidget

    from ui.settings import SettingsWindow

    app = QApplication.instance() or QApplication([])
    settings, secrets, ui_json = _make_settings_files(tmp_path)
    win = SettingsWindow(settings, secrets, ui_json)
    tabs = win.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.count() == 5
    titles = {tabs.tabText(i) for i in range(tabs.count())}
    assert titles == {"Genel", "Sağlayıcı", "Ekran kontrolü", "İzinler", "Avatar"}
    win.hide()
    win.deleteLater()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ui/test_settings.py::test_settings_has_five_titled_tabs -v`
Expected: FAIL — no QTabWidget.

- [ ] **Step 3: Restructure the layout**

In `SettingsWindow.__init__` (`ui/settings.py`), replace the direct `layout.addWidget(general_box)` sequence with a `QTabWidget`:

- `tabs = QTabWidget(self)`; `tabs.addTab(general_box, i18n.t("settings.section_general"))`, then provider → `settings.section_provider`, screen → `settings.section_screen`, permissions → `settings.section_permissions`, avatar → `settings.section_avatar`.
- Add `tabs` to the main layout in place of the five boxes; `_status` and the button row keep their positions after it.
- Do not rename any widget attributes; do not touch `_save`/`load` logic.

- [ ] **Step 4: Run tests and the whole suite**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ui/test_settings.py -q && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests -q`
Expected: PASS — existing save/load tests keep working because attribute names are unchanged.

- [ ] **Step 5: Commit**

```bash
git add ui/settings.py tests/ui/test_settings.py
git commit -m "feat(settings): restructure into five titled tabs"
```

---

### Task 5: Chat history deletion

**Files:**
- Modify: `ui/i18n.py` (three new keys)
- Modify: `ui/gui/main_window.py` (context menu, `_confirm_delete_session`, `_delete_session`, guards in append handlers)
- Test: `tests/ui/test_chat.py` (extend)

**Interfaces:**
- Consumes: `HistoryStore.delete_session(session_id)` (`ui/history.py:105`); `ChatWindow._busy`, `_runtime.cancel_active_task()` (`core/agent/runtime.py:154`); `_clear_messages()`/`_reload_sessions()`/`new_chat()` from Task 3 (empty-state restore included).
- Produces: module-level `confirm_delete_session(parent, title: str) -> bool` in `main_window.py` (monkeypatch seam for tests); `ChatWindow._delete_session(session_id: str) -> None`; `ChatWindow._on_session_menu(pos) -> None`.

- [ ] **Step 1: Add i18n keys**

```python
"sessions.delete": {"tr": "Sohbeti sil", "en": "Delete chat"},
"sessions.delete_confirm": {
    "tr": "'{title}' sohbeti kalıcı olarak silinsin mi?",
    "en": "Permanently delete the '{title}' chat?",
},
"sessions.delete_cancel": {"tr": "Vazgeç", "en": "Cancel"},
```

- [ ] **Step 2: Write the failing tests**

Extend `tests/ui/test_chat.py` (reuse `_make_window`, `FakeRuntime`):

```python
def _seed_sessions(win, n=2):
    ids = []
    for i in range(n):
        sid = win._history.create_session()
        win._history.append(sid, "user", f"selam {i}")
        ids.append(sid)
    win._reload_sessions()
    return ids


def test_context_menu_delete_removes_session(tmp_path, monkeypatch):
    import ui.gui.main_window as mw

    app, win = _make_window(tmp_path)
    sids = _seed_sessions(win)
    monkeypatch.setattr(mw, "confirm_delete_session", lambda parent, title: True)
    win._delete_session(sids[0])
    remaining = [s[0] for s in win._history.list_sessions()]
    assert sids[0] not in remaining
    assert win._sessions.count() == len(remaining)
    win.hide()


def test_cancelled_confirm_keeps_session(tmp_path, monkeypatch):
    import ui.gui.main_window as mw

    app, win = _make_window(tmp_path)
    sids = _seed_sessions(win, 1)
    monkeypatch.setattr(mw, "confirm_delete_session", lambda parent, title: False)
    win._delete_session(sids[0])
    assert sids[0] in [s[0] for s in win._history.list_sessions()]
    win.hide()


def test_delete_active_session_resets_to_empty(tmp_path, monkeypatch):
    import ui.gui.main_window as mw

    app, win = _make_window(tmp_path)
    sids = _seed_sessions(win, 1)
    win._load_session(sids[0])
    assert win._session_id == sids[0]
    monkeypatch.setattr(mw, "confirm_delete_session", lambda parent, title: True)
    win._delete_session(sids[0])
    assert win._session_id is None
    assert win._messages == []
    assert not win._empty_state.isHidden()
    win.hide()


def test_delete_active_while_running_cancels_task(tmp_path, monkeypatch):
    import ui.gui.main_window as mw

    app, win = _make_window(tmp_path)
    sids = _seed_sessions(win, 1)
    win._load_session(sids[0])
    win._set_busy(True)

    calls = []
    win._runtime = type("R", (), {"cancel_active_task": lambda self: calls.append("cancel")})()
    monkeypatch.setattr(mw, "confirm_delete_session", lambda parent, title: True)
    win._delete_session(sids[0])
    assert calls == ["cancel"]
    assert win._session_id is None
    win.hide()


def test_delete_active_while_running_no_late_append(tmp_path, monkeypatch):
    """A cancelled-signal arriving after deletion must not crash or resurrect."""
    import ui.gui.main_window as mw

    app, win = _make_window(tmp_path)
    sids = _seed_sessions(win, 1)
    win._load_session(sids[0])
    win._set_busy(True)
    win._runtime = type("R", (), {"cancel_active_task": lambda self: None})()
    monkeypatch.setattr(mw, "confirm_delete_session", lambda parent, title: True)
    win._delete_session(sids[0])
    # late signal handlers (as if the agent thread just noticed the cancel)
    win._on_cancelled()
    win._on_finished()
    assert win._history.messages(sids[0]) == []  # nothing appended after delete
    win.hide()


def test_send_after_delete_creates_new_session(tmp_path, monkeypatch):
    import ui.gui.main_window as mw

    app, win = _make_window(tmp_path)
    win._runtime = FakeRuntime(win)
    sids = _seed_sessions(win, 1)
    win._load_session(sids[0])
    monkeypatch.setattr(mw, "confirm_delete_session", lambda parent, title: True)
    win._delete_session(sids[0])
    win._chat_input.setPlainText("yeni mesaj")
    win._send()
    assert win._session_id is not None
    assert win._session_id != sids[0]
    assert ("user", "yeni mesaj", None) in win._history.messages(win._session_id)
    win.hide()


def test_confirm_delete_session_builds_dialog_with_danger_button():
    """The confirm helper builds a dialog with filled-danger delete + outline cancel."""
    from PySide6.QtWidgets import QApplication, QDialogButtonBox, QPushButton

    from ui.gui.main_window import _build_delete_dialog

    app = QApplication.instance() or QApplication([])
    dlg = _build_delete_dialog(None, "deneme sohbeti")
    buttons = dlg.findChild(QDialogButtonBox)
    assert buttons is not None
    danger = buttons.button(QDialogButtonBox.StandardButton.Yes)
    cancel = buttons.button(QDialogButtonBox.StandardButton.No)
    assert danger is not None and danger.objectName() == "danger"
    assert cancel is not None and cancel.objectName() == "outline"
    dlg.deleteLater()
```

(The last test only pins importability; dialog interaction is covered by the monkeypatched seams.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ui/test_chat.py -v -k "delete or cancelled_confirm or send_after"`
Expected: FAIL — `confirm_delete_session` / `_delete_session` do not exist.

- [ ] **Step 4: Implement**

In `ui/gui/main_window.py`:

- Module-level `_build_delete_dialog(parent, title: str) -> QDialog`: builds a
  `QDialog` (windowTitle `sessions.delete`), a word-wrapped QLabel with
  `sessions.delete_confirm.format(title=title)`, and a `QDialogButtonBox` with
  Yes (text `sessions.delete`, objectName `danger`) and No (text
  `sessions.delete_cancel`, objectName `outline`). Style via the app QSS
  (objectNames from Task 1).
- Module-level `confirm_delete_session(parent, title: str) -> bool`: calls
  `_build_delete_dialog`, returns `dlg.exec() == QDialog.DialogCode.Accepted`.
- `ChatWindow._on_session_menu(pos)`: `item = self._sessions.itemAt(pos)`; if None return; `menu = QMenu(self._sessions)`; `act = menu.addAction(i18n.t("sessions.delete"))`; if `menu.exec(self._sessions.mapToGlobal(pos)) == act` → `self._delete_session(item.data(Qt.ItemDataRole.UserRole))`.
- In `__init__`: `self._sessions.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)`; connect `customContextMenuRequested` to `_on_session_menu`.
- `ChatWindow._delete_session(session_id: str) -> None`:
  1. Resolve the display title: scan `self._history.list_sessions()` for the
     tuple whose first element equals `session_id`; use its title, falling
     back to `session_id[:8]`. If `confirm_delete_session(self, title)` is
     False → return without deleting.
  2. `was_active = session_id == self._session_id`.
  3. If `was_active and self._busy and self._runtime is not None`: call
     `self._runtime.cancel_active_task()` then `self._set_busy(False)`.
  4. `self._history.delete_session(session_id)`.
  5. If `was_active`: `self._session_id = None`; `self._clear_messages()`
     (restores the empty state via Task 3); `self._chat_input.setFocus()`.
  6. `self._reload_sessions()`.

- **Late-signal guards** (Review Focus #1): at the top of `_on_assistant`, `_on_error`, `_on_cancelled`, skip the `self._history.append(...)` call when `self._session_id is None` (the transcript widget may still show the line; only persistence is skipped). `_on_finished` needs no guard (it only reloads sessions).

- [ ] **Step 5: Run tests and the whole suite**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ui/test_chat.py -q && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/gui/main_window.py ui/i18n.py tests/ui/test_chat.py
git commit -m "feat(gui): right-click chat deletion with confirmation and active-task cancel"
```

---

### Task 6: Final verification

**Files:**
- None new; verification only.

- [ ] **Step 1: Full suite + compile pass**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests -q
.venv/bin/python -m py_compile ui/theme.py ui/fonts.py ui/gui/main_window.py ui/settings.py ui/i18n.py
```

Expected: all tests PASS; compile OK.

- [ ] **Step 2: Smoke-launch the GUI offscreen**

```bash
QT_QPA_PLATFORM=offscreen timeout 5 .venv/bin/python -c "
from PySide6.QtWidgets import QApplication
from ui.theme import apply_theme, qss
from ui.fonts import load_fonts
app = QApplication([])
apply_theme(app, 'dark'); apply_theme(app, 'light')
print('font id', load_fonts(app))
"
```

Expected: prints a font id != -1; no exceptions.

- [ ] **Step 3: Commit any loose ends (or skip when clean)**

If verification surfaced small fixes, commit them with a `fix:` message; otherwise proceed.

- [ ] **Step 4: Append completion ledger**

Append Task 1–6 completion lines to `.superpowers/sdd/2026-10-10-gui-renewal/progress.md` (create the directory as part of execution setup via the executing-plans / subagent-driven-development skill).

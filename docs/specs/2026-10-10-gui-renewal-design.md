# GUI Renewal and Chat Deletion — Design Spec

Date: 2026-10-10
Status: revised after user review (v2), awaiting approval
Repo: desktop-assistant (PySide6)

## 1. Goal

Radically renew the visual design of the desktop AI assistant GUI and add a
chat-history deletion feature. The renewal uses a soft/pastel aesthetic in light
mode and a near-black aesthetic in dark mode, grounded in the app's identity
(the Teto avatar) rather than generic AI-generated design defaults. Design
guidance follows the installed `frontend-design`, `landing-page-design`, and
`better-interface` skills.

## 2. Constraints

- `core/` remains Qt-free; this work touches `ui/` and `assets/` only.
- The `REQUIRED_OBJECTNAMES` theme contract (`ui/theme.py`) stays valid; any
  new objectNames are added to the contract and its test.
- i18n: all new user-facing strings added to `ui/i18n.py` in both `tr` and `en`.
  Turkish for chat, English for code/commits/docs.
- All existing tests (currently 191) stay green; new behavior gets new tests.
- TDD workflow: RED test first, then GREEN, per-task commits.
- Contrast: every text/background pair meets WCAG AA (>= 4.5:1 body text);
  input borders meet the UI-component 3:1 rule.

## 3. Design decisions (confirmed)

| Decision | Choice | Rationale |
|---|---|---|
| Direction | Radical renewal | User choice |
| Mood | Soft/pastel (light), near-black (dark) | User choice |
| Dark background | `#0D0D0D` base | "siyahımsı" request; one step darker than the design skill's `#181818` floor for the window base |
| Dark borders | `#2E2E2E` | Raised from `#272727` so layers separate optically (user review: `#272727` vs `#181818` was only 1.08–1.30:1) |
| Accent (dark) | `#F87171` | Teto-red; 6.82:1 against `on_accent` |
| Accent (light) | `#D1433B` | Darkened from `#E5534B` for AA: 4.59:1 against white |
| Typeface | Nunito, bundled in-repo | Rounded terminals match the soft brief; full Turkish glyphs; bundled so the choice never silently falls back |
| Chat deletion UX | Right-click context menu on session items | User choice |

## 4. Design tokens

All values live in `ui/theme.py` as a `THEMES` palette extension plus QSS
constants. Dark and light each define the same token set.

### 4.1 Color tokens

Dark mode:

| Token | Value | Use |
|---|---|---|
| `bg` | `#0D0D0D` | Window background |
| `bg_alt` | `#181818` | Sidebar, panels |
| `surface` | `#1F1F1F` | Cards, assistant bubbles, inputs |
| `surface_hover` | `#272727` | Hover states |
| `border` | `#2E2E2E` | Panel/card borders, separators |
| `input_border` | `#5C5C62` | Input/control borders (meets 3:1 UI-component rule) |
| `fg` | `#F2F2F2` | Primary text |
| `fg_muted` | `#8E8E93` | Secondary text |
| `accent` | `#F87171` | Accent, links, active states |
| `accent_hover` | `#FA8A8A` | Accent hover |
| `bubble_user` | `#2A1B1B` | User message bubble |
| `bubble_assistant` | `#1F1F1F` | Assistant message bubble |
| `danger` | `#FF4D4D` | Destructive controls only (filled) |
| `on_accent` | `#1A0E0E` | Text on accent fill (6.82:1) |
| `on_danger` | `#FFFFFF` | Text on danger fill |

Light mode:

| Token | Value |
|---|---|
| `bg` | `#F6F6F7` |
| `bg_alt` | `#FFFFFF` |
| `surface` | `#FFFFFF` |
| `surface_hover` | `#EFEFF1` |
| `border` | `#E2E2E5` |
| `input_border` | `#8E8E93` |
| `fg` | `#17171A` |
| `fg_muted` | `#6B6B70` |
| `accent` | `#D1433B` |
| `accent_hover` | `#B93530` |
| `bubble_user` | `#FDECEC` |
| `bubble_assistant` | `#FFFFFF` |
| `danger` | `#C93636` |
| `on_accent` | `#FFFFFF` (4.59:1 on `#D1433B`) |
| `on_danger` | `#FFFFFF` |

Rules:
- No background gradients; borders always all four sides or none.
- Destructive controls are always **filled** danger with a light label.
  Outline-danger next to accent-filled controls is forbidden (shape, not hue,
  carries the destructive signal — dark `#F87171` vs a red danger differ by
  only 1.36:1).
- Selected session item = accent fill + `on_accent` text (not accent-colored
  text on a tint, which failed contrast).
- `input_border` is used wherever a control's only affordance is its border
  (text inputs, combos); decorative panel borders stay on `border`.

### 4.2 Typography

- Family: Nunito, **bundled at `assets/fonts/Nunito.ttf`** (OFL license) and
  loaded at startup via `QFontDatabase.addApplicationFont`. QSS and `QFont`
  use `"Nunito", sans-serif` so a missing file degrades gracefully but the
  bundled file is the norm. The PyInstaller spec already collects `assets/`;
  verify no spec change is needed.
- Base size: 10pt. Weights: Normal and Bold only; no ultra-bold, no italics.
- Sentence case for all labels and headers.

### 4.3 Radii and spacing

- Nested-radius rule: when an element sits inside another with a gap < 32px,
  `inner_radius = outer_radius - gap` (skip if result <= 2).
- Radii: windows/panels 0; cards/bubbles 14px; inputs/buttons 10px; pill
  buttons 999px.
- Spacing scale (px): 4, 8, 12, 16, 24, 32. No ad-hoc values in QSS.

### 4.4 Motion and focus (Qt-realistic)

- **No QSS transitions** (unsupported). Hover feedback is an immediate color
  change. A QPropertyAnimation-based polish pass is a possible follow-up, not
  in scope.
- **Focus ring**: implemented as a persistent 2px border on interactive
  widgets (normal state border uses a color that reserves the same 2px, so
  there is no size jump) that switches to `accent` on `:focus`. This is the
  Qt-reliable equivalent of an outline.
- Press/depress 1px offset: skipped (not reliable in QSS).

## 5. Component designs

### 5.1 Main window (`ui/gui/main_window.py`)

Layout skeleton unchanged (sidebar + chat column); visual treatment changes.

**Sidebar:**
- Header label "Sohbetler" / "Chats" (the orphaned `sidebar.sessions` i18n
  key, finally wired).
- "Yeni sohbet" / "New chat" as an accent pill button at top.
- Session items: card-style, 10px radius, 8px margins; hover =
  `surface_hover`; selected = accent fill + `on_accent` text.
- Bottom action buttons (theme, settings, avatar, collapse): quiet text
  rows, hover-tinted.

**Chat area:**
- Message bubbles: 14px radius cards; user bubbles right-aligned in
  `bubble_user`; assistant bubbles left-aligned in `bubble_assistant`; tool
  messages as muted full-width strips (`fg_muted`, thin border).
- Scroll area: thin rounded scrollbar (QSS `QScrollBar`, 8px wide, `border`
  track, `surface_hover` thumb).
- Activity label: `fg_muted`, small.

**Input row:**
- Rounded 14px card wrapping the QPlainTextEdit; send = accent-filled pill;
  cancel = **neutral outline** (never outline-danger beside an accent fill).
- Enter sends, Shift+Enter newline (existing behavior preserved).

**Empty state (new):**
- When no session/messages: centered composed panel — greeting line
  ("Merhaba! Bir sohbet başlat." / "Hi! Start a chat."), one hint line,
  accent-tinted. Never a blank panel.

### 5.2 Settings window (`ui/settings.py`)

- Restructure the vertical QGroupBox stack into a `QTabWidget` with five tabs:
  Genel/General, Model, Ekran/Screen, İzinler/Permissions, Avatar. Each tab
  hosts the existing form rows with visible titles (fixes the untitled
  groupbox defect).
- Save/Close button row stays at the bottom, outside the tab widget.
- Pack-build/delete behavior unchanged (worker thread, user-dir logic).

### 5.3 Chat deletion feature (new, `ui/gui/main_window.py` + i18n)

- Right-click on a session item shows a `QMenu`: "Sohbeti sil" / "Delete chat".
- Confirmation dialog (pastel styling): question `sessions.delete_confirm`;
  "Sil"/"Delete" = **filled danger**; "Vazgeç"/"Cancel" = neutral outline.
- On confirm:
  1. If the target session is the active one **and a task is running** in the
     runtime, cancel the running task first via the existing cancel path
     (the same mechanism as the cancel button).
  2. `HistoryStore.delete_session(sid)` (exists, `ui/history.py:105`).
  3. Reload the session list.
  4. If the deleted session was active: reset to the empty/new-chat state.
     This must also drop the runtime's association with the session (same
     reset `new_chat()` performs) so the in-memory `core.session.store.
     SessionStore` cannot keep referencing the deleted session — the runtime
     store is separate from `HistoryStore`; verify on delete that no message
     append can target the deleted id.
- New i18n keys: `sessions.delete`, `sessions.delete_confirm`,
  `sessions.delete_confirm_title`.
- No bulk deletion (out of scope).

### 5.4 Bubble window (`ui/bubble.py`) and dialogs

- Bubble window adopts the same tokens (radii/spacing match the new scale).
- `ModeChooser` and the tool-confirmation dialog inherit the app QSS; add
  objectNames if needed so QSS targets them (extend the contract).

## 6. Accessibility

- Visible focus ring (2px `accent` border swap, section 4.4) on every
  interactive widget.
- Keyboard path: session items actionable via the context-menu key;
  confirmation dialog fully keyboard operable (QDialogButtonBox default).
- Contrast (computed, not aspirational):
  - Dark: `fg`/`bg` 15+:1; `on_accent`/`accent` 6.82:1; `on_danger`/`danger`
    ~4.6:1.
  - Light: `fg`/`bg` 15+:1; `on_accent`/`accent` (`#FFFFFF`/`#D1433B`) 4.59:1;
    `on_danger`/`danger` (`#FFFFFF`/`#C93636`) ~5.2:1.
  - Input borders (`input_border`) >= 3:1 against their surrounding
    background on both themes.
- Destructive actions always confirm; destructive controls are filled and
  never share a row with an accent-filled control.

## 7. Testing

- Keep the objectName contract test green; extend for new names.
- New tests:
  - Right-click delete flow: menu action triggers confirm; confirm calls
    `delete_session` and refreshes; deleting the active session resets the
    transcript and the runtime session association (UI test, offscreen).
  - Cancel path: dialog cancel does not delete.
  - Active-task path: deleting the active session while a task is running
    cancels the task before deletion (stub the runtime).
  - i18n: new keys present in both languages (fail-loud i18n raises on miss).
  - Theme: QSS builder emits rules for new tokens; both themes construct;
    `input_border` and focus rules present.
  - Font: `assets/fonts/Nunito.ttf` exists and loads via QFontDatabase in a
    test (offscreen).
- Full suite run after each task; final run before commit.

## 8. Out of scope

- The 12 reviewer findings from the P0 vision/avatar review (addressed after
  this renewal).
- Bulk history deletion.
- QPropertyAnimation-based transitions and press feedback (nice-to-have
  follow-up).
- Avatar sprite art changes (only window/bubble chrome follows the palette).
- Windows-specific chrome tuning beyond what QSS provides.

## 9. Resolved from user review (v1 → v2)

1. Dark layer separation: `border` raised to `#2E2E2E`.
2. Nunito bundling moved into scope (`assets/fonts/Nunito.ttf` +
   `QFontDatabase.addApplicationFont`).
3. Light accent darkened to `#D1433B` (AA-passing); selected session uses
   accent fill, not accent text on tint.
4. Input/control borders use `input_border` (3:1 UI-component rule).
5. Destructive signal carried by filled-danger shape; neutral outline for
   cancel; rule against outline-danger beside accent fills.
6. QSS motion claims removed; focus ring re-specified Qt-realistically.
7. Deletion of a running-task session cancels the task first; runtime
   SessionStore association reset specified.

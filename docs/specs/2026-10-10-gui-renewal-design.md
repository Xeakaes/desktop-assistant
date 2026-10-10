# GUI Renewal and Chat Deletion — Design Spec

Date: 2026-10-10
Status: awaiting user review
Repo: desktop-assistant (PySide6)

## 1. Goal

Radically renew the visual design of the desktop AI assistant GUI and add a
chat-history deletion feature. The renewal uses a soft/pastel aesthetic in light
mode and a near-black aesthetic in dark mode, grounded in the app's identity
(the Teto avatar) rather than generic AI-generated design defaults. Design
guidance follows the installed `frontend-design`, `landing-page-design`, and
`better-interface` skills.

## 2. Constraints

- `core/` remains Qt-free; this work touches `ui/` only.
- The `REQUIRED_OBJECTNAMES` theme contract (`ui/theme.py`) stays valid; any
  new objectNames are added to the contract and its test.
- i18n: all new user-facing strings added to `ui/i18n.py` in both `tr` and `en`.
  Turkish for chat, English for code/commits/docs.
- All existing tests (currently 191) stay green; new behavior gets new tests.
- TDD workflow: RED test first, then GREEN, per-task commits.

## 3. Design decisions (confirmed during brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| Direction | Radical renewal | User chose over incremental polish |
| Mood | Soft / pastel (light), near-black (dark) | User choice |
| Dark background | `#0D0D0D` base | User asked for "siyahımsı"; one step darker than the landing-page-design skill's `#181818` floor for the window base; panels use the skill's scale |
| Accent | Soft coral/red `#F87171` (dark) / `#E5534B` (light) | Grounded in the Teto identity (red-haired character); avoids the templated purple AI-default |
| Typeface | Nunito (bundled via QFont; falls back to system sans) | Rounded terminals match the soft brief; full Turkish glyph support |
| Chat deletion UX | Right-click context menu on session items | User choice over inline × button |

## 4. Design tokens

All values live in `ui/theme.py` as a `THEMES` palette extension plus QSS
constants. Dark and light each define the same token set.

### 4.1 Color tokens

Dark mode (near-black scale per landing-page-design B4, with `#0D0D0D` base):

| Token | Value | Use |
|---|---|---|
| `bg` | `#0D0D0D` | Window background |
| `bg_alt` | `#181818` | Sidebar, panels |
| `surface` | `#1F1F1F` | Cards, bubbles (assistant), inputs |
| `surface_hover` | `#272727` | Hover states |
| `border` | `#272727` | Borders, separators |
| `fg` | `#F2F2F2` | Primary text |
| `fg_muted` | `#8E8E93` | Secondary text |
| `accent` | `#F87171` | Accent, links, focus ring, active states |
| `accent_hover` | `#FA8A8A` | Accent hover |
| `bubble_user` | `#2A1B1B` | User message bubble (red-tinted dark) |
| `bubble_assistant` | `#1F1F1F` | Assistant message bubble |
| `danger` | `#EF4444` | Destructive actions only |
| `on_accent` | `#1A0E0E` | Text on accent-filled buttons |

Light mode (soft/pastel):

| Token | Value |
|---|---|
| `bg` | `#F6F6F7` |
| `bg_alt` | `#FFFFFF` |
| `surface` | `#FFFFFF` |
| `surface_hover` | `#EFEFF1` |
| `border` | `#E2E2E5` |
| `fg` | `#17171A` |
| `fg_muted` | `#6B6B70` |
| `accent` | `#E5534B` |
| `accent_hover` | `#D1433B` |
| `bubble_user` | `#FDECEC` |
| `bubble_assistant` | `#FFFFFF` |
| `danger` | `#DC2626` |
| `on_accent` | `#FFFFFF` |

Rules: no background gradients; borders always all four sides or none;
danger hue only on destructive controls.

### 4.2 Typography

- Family: Nunito for all UI text (QSS `font-family` + `QFont` on widgets that
  need explicit setting). Fallback chain: `"Nunito", sans-serif`.
- Base size: 10pt (~13–14px rendered). Weights limited to Normal and Bold
  (600–700 effective); no ultra-bold, no italics.
- Sentence case for all labels and headers.

### 4.3 Radii and spacing

- Nested-radius rule: when an element sits inside another with a gap < 32px,
  `inner_radius = outer_radius - gap` (skip if result <= 2).
- Radii: windows/panels 0; cards/bubbles 14px; inputs/buttons 10px; pill
  buttons 999px.
- Spacing scale (px): 4, 8, 12, 16, 24, 32. No ad-hoc values in QSS.

### 4.4 Motion

- Hover/active transitions: 120ms; active press feel via 1px content offset
  where Qt allows. No decorative auto-playing motion.
- Focus ring: 2px `accent` outline, visible on every interactive widget.

## 5. Component designs

### 5.1 Main window (`ui/gui/main_window.py`)

Layout skeleton unchanged (sidebar + chat column); visual treatment changes.

**Sidebar:**
- Header label "Sohbetler" / "Chats" (uses the orphaned `sidebar.sessions`
  i18n key, finally wired).
- "Yeni sohbet" / "New chat" as an accent pill button at top.
- Session items: card-style with 10px radius, 8px margins; hover =
  `surface_hover`; selected = accent-tinted background with accent text.
- Bottom action buttons (theme, settings, avatar, collapse): quiet rows,
  icon-free text for now (no icon dependency), hover-tinted.

**Chat area:**
- Message bubbles: 14px radius cards; user bubbles right-aligned in
  `bubble_user`; assistant bubbles left-aligned in `bubble_assistant`; tool
  messages as muted full-width strips with monospace-ish treatment via
  `fg_muted` and thinner border.
- Scroll area: thin rounded scrollbar (QSS `QScrollBar` rules, 8px wide,
  `border`-colored track, `surface_hover` thumb).
- Activity label: `fg_muted`, small.

**Input row:**
- Rounded 14px card wrapping the QPlainTextEdit; send button accent-filled
  pill; cancel button outline danger. Enter sends, Shift+Enter newline
  (existing behavior preserved).

**Empty state (new):**
- When no session/messages: centered composed panel — short greeting line
  ("Merhaba! Bir sohbet başlat." / "Hi! Start a chat."), one hint line about
  asking the assistant, accent-tinted. Never a blank panel.

### 5.2 Settings window (`ui/settings.py`)

- Restructure the vertical QGroupBox stack into a `QTabWidget` with five tabs:
  Genel/General, Model/Provider, Ekran/Screen control, İzinler/Permissions,
  Avatar. Each tab hosts the existing form rows with visible section titles
  (fixes the untitled-groupbox defect).
- Save/Close button row stays at the bottom, outside the tab widget.
- Pack-build/delete behavior unchanged (worker thread, user-dir logic).

### 5.3 Chat deletion feature (new, `ui/gui/main_window.py` + i18n)

- Right-click (contextMenuEvent) on a session item in the sidebar list shows
  a `QMenu` with one action: "Sohbeti sil" / "Delete chat".
- Activating it opens a confirmation dialog (pastel styling, modeled on the
  existing avatar-pack delete confirmation): question text
  `sessions.delete_confirm`, buttons "Sil"/"Delete" (danger) and
  "Vazgeç"/"Cancel".
- On confirm: `HistoryStore.delete_session(sid)` (already exists,
  `ui/history.py:105`), then reload the session list. If the deleted session
  was the active one, reset to the empty/new-chat state.
- New i18n keys: `sessions.delete`, `sessions.delete_confirm`,
  `sessions.delete_confirm_title`.
- No bulk deletion (out of scope).

### 5.4 Bubble window (`ui/bubble.py`) and dialogs

- Bubble window adopts the same tokens (it already reads from the theme QSS;
  verify radii/spacing match the new scale).
- `ModeChooser` and the tool-confirmation dialog inherit the app QSS; add
  objectNames if needed so QSS targets them (extend the contract).

## 6. Accessibility

- Visible focus ring on every interactive widget (currently missing entirely).
- Keyboard path: session items reachable and actionable via keyboard menu key;
  confirmation dialog fully keyboard operable (QDialogButtonBox default).
- Contrast: `fg`/`bg` and `accent`/`on_accent` pairs meet WCAG AA (>= 4.5:1
  body text, >= 3:1 large text and UI components). Values in section 4 were
  chosen to satisfy this; verified during implementation review with the
  `better-interface` skill.
- Destructive action (delete chat) always confirms before executing.

## 7. Testing

- Keep the objectName contract test green; extend it for any new names.
- New tests:
  - Right-click delete flow: menu action triggers confirm; confirm calls
    `delete_session` and refreshes; deleting the active session resets the
    transcript (UI test, offscreen).
  - Cancel path: dialog cancel does not delete.
  - i18n: new keys present in both languages (fail-loud i18n raises on miss).
  - Theme: QSS builder emits rules for new tokens; both themes construct
    without error.
- Full suite run after each task; final run before commit.

## 8. Out of scope

- The 12 reviewer findings from the P0 vision/avatar review (tracked
  separately; will be addressed after this renewal).
- Bulk history deletion.
- Font-file bundling into the PyInstaller artifact (Nunito via QFont with
  system fallback; bundling is a follow-up if the font is missing).
- Avatar sprite art changes (only window/bubble chrome follows the palette).
- Windows-specific chrome tuning beyond what QSS provides.

## 9. Open points for user review

1. Dark base `#0D0D0D` (slightly darker than the design skill's `#181818`
   floor) — chosen to honor the "siyahımsı" request; say if you prefer the
   skill's exact `#181818`.
2. Accent `#F87171` / `#E5534B` (Teto-red) — confirm the hue, or name a
   preferred color.
3. Nunito as the UI font — confirm, or name a preference (Manrope/Poppins are
   the skill's defaults).

# Packaging & GitHub Release Design

**Date:** 2026-10-09
**Status:** Approved
**Milestone:** M2 (post full-GUI)

## Goal

Ship a self-contained Desktop AI Assistant:

- **Linux:** `.deb` package + portable tar.gz (PyInstaller onedir).
- **Windows:** `.zip` with `.exe` (PyInstaller onedir) — built on GitHub Actions `windows` runner, no local Windows machine required.
- **Public GitHub repo** `Xeakaes/desktop-assistant` (Actions free tier is unlimited on public repos).
- **Self-contained tooling:** the screen-control SDK + server are bundled inside the package; end users install nothing beyond the package itself.

## Non-goals

- Auto-update mechanism.
- Code signing / notarization (deferred).
- OCR (rapidocr) bundled in default profile (~200MB) — optional later.
- Homebrew / AUR / Microsoft Store distribution.

## Constraints

- `core/` stays Qt-free (`tests/ui/test_qt_free_core.py`).
- Existing 123 tests stay green; new packaging code is covered by new tests.
- `config/secrets.json` never enters the bundle, the repo, or CI logs.
- Mode/theme/lang prefs, history DB, and server tokens live in the **user config/data dirs** at runtime — never inside the read-only bundle.
- Development workflow (`python -m ui.app`, `cli.py`, `pytest`) keeps working unchanged from a source checkout.

## Architecture

### 1. Config / asset path resolution (frozen-aware)

Single module `core/paths.py`:

```python
def is_frozen() -> bool:
    return getattr(sys, "frozen", False)

def bundle_root() -> Path:
    # PyInstaller onedir/onefile extract dir; falls back to repo root in dev
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))

def config_dir() -> Path:
    if is_frozen():
        # Linux: ~/.config/desktop-assistant  |  Windows: %APPDATA%/desktop-assistant
        ...
    return repo_root / "config"   # dev: unchanged behavior

def data_dir() -> Path:
    # ~/.local/share/desktop-assistant (Linux) / %APPDATA% (Windows) — history.db
```

- `core/bootstrap.py` replaces hard-coded `ROOT / "config"` with `core.paths.config_dir()`.
- `ui/paths.py` imports from `core.paths` (no duplicate logic).
- `ui/avatar_app.py` and pack builder resolve `assets/` via `core.paths.bundle_root() / "assets"`.

### 2. Bundled screen-control

- **Vendor:** copy `screen_control.py` (68K client SDK) into `vendor/screen_control/screen_control.py`. `core/tools/screen_control.py` and `default_client_factory` import from `vendor.screen_control` (repo adds `vendor/` to `sys.path` in dev; PyInstaller collects it as a package).
- **Server:** the main entry (`ui/app.py` / `ui/avatar_app.py` `main()`) gains a `--serve-screen-control` flag. When screen-control is `enabled` in settings and port 8745 is not listening, the app re-spawns itself:
  ```
  subprocess.Popen([sys.executable_or_frozen_exe, "--serve-screen-control"], ...)
  ```
  The server mode imports `vendor`-shipped server modules (flask, mss, pyautogui, Pillow, numpy, platform backends) and runs the HTTP API on 127.0.0.1:8745.
- **Server code vendor:** the server + `backends/` + `core/` server modules from `/home/xeakaes/screen-control` are copied into `vendor/screen_control/server/` (same license header preserved). The assistant never reaches outside the bundle at runtime.
- **Tokens:** `.token` / `.apikeys` are written to `config_dir()` (user-writable), never to the bundle.

### 3. PyInstaller

- One **spec file** `packaging/desktop-assistant.spec` shared by both OS runners.
- Mode: `onedir` (COLLECT) — more stable with Qt plugins than onefile, easier to debug, fewer AV false positives.
- `datas`: `assets/`, `vendor/screen_control/`, default `config/settings.json` **template only** (no secrets) as `config_template/`.
- Hidden imports: PySide6 plugins, flask, mss, pyautogui, PIL, numpy, evdev (linux-only conditional), pyvda (win32-only conditional).
- Entry: a thin `packaging/entry.py` that parses `--serve-screen-control` and dispatches to either `ui.avatar_app.main` / `ui.app.main` (per current prefs mode) or the bundled server runner.
- Icon: `packaging/icon.ico` (Windows) + `packaging/icon.png` (Linux).

### 4. Debian package

- Built with `nfpm` (single static Go binary, no Ruby/gem dependency) from `packaging/nfpm.yaml`.
- Package name: `desktop-assistant`; arch: `amd64`; maintainer: Xeakaes.
- Installs the PyInstaller onedir output under `/opt/desktop-assistant/` and a `.desktop` entry + icon under `/usr/share/applications/` and `/usr/share/icons/`.
- `postinst`: nothing privileged beyond file placement; no service registration (app is user-session).
- Also ship a portable `.tar.gz` of the same onedir for users who don't want dpkg.

### 5. GitHub repository

- Create public repo `desktop-assistant` under the authenticated account (git credential helper is already stored; `gh` CLI is absent — repo creation via GitHub REST API using a personal access token, or instruct the user to create the repo and we push. **Decision:** attempt API create with stored credentials; if no API token available, push to a user-created repo).
- Push `main` (all existing commits) + packaging commits.
- Add `README.md` (install/run/build from source), `LICENSE` (MIT unless user says otherwise — **assumed MIT, flag in review**), `.gitignore` already covers `config/secrets.json`.

### 6. GitHub Actions — release workflow

`.github/workflows/release.yml`:

- **Trigger:** `push: tags: ["v*"]` and `workflow_dispatch` (manual).
- **Job `build-linux`** (`ubuntu-latest`):
  1. Checkout, setup Python 3.12, install `requirements.txt` + pyinstaller + nfpm.
  2. `pyinstaller packaging/desktop-assistant.spec`
  3. `nfpm package --packager deb` → `desktop-assistant_<version>_amd64.deb`
  4. `tar -czf desktop-assistant_<version>_linux_amd64.tar.gz` of the onedir.
  5. Upload both as artifacts.
- **Job `build-windows`** (`windows-latest`):
  1. Checkout, setup Python 3.12, install deps + pyinstaller.
  2. `pyinstaller packaging/desktop-assistant.spec`
  3. `Compress-Archive` → `desktop-assistant_<version>_windows_amd64.zip`
  4. Upload artifact.
- **Job `release`** (needs both, `if: startsWith(github.ref, 'refs/tags/')`):
  - Download artifacts, `softprops/action-gh-release` (or `gh release create`) attaches deb/tar.gz/zip to a GitHub Release for the tag.
- Version string comes from the tag (`github.ref_name` stripped of `v`) injected as env `APP_VERSION`, read by the spec/`entry.py` for `--version` display.

### 7. Versioning & CLI

- `core/__init__.py` gains `__version__ = "0.0.0"`; build overwrites it or entry reads `APP_VERSION` env / `_version.txt` bundled by the spec.
- `cli.py` and `ui/app.py` accept `--version` printing the baked version.

## Data flow (runtime, frozen)

```
User launches desktop-assistant(.exe)
  └─ entry.py parses argv
       ├─ --serve-screen-control → vendor server runner (flask on :8745, tokens in config_dir)
       └─ else → ui.app.main()
            ├─ load prefs from config_dir()/ui.json
            ├─ first-run → ModeChooser; persist mode
            ├─ if screen-control enabled and :8745 not up → spawn self --serve-screen-control
            ├─ build_runtime() → config_dir()/settings.json + secrets.json
            ├─ theme applied; GUI or Avatar window
            └─ history DB at data_dir()/history.db
```

## Error handling

- Frozen launch with missing/corrupt `settings.json`: fall back to bundled `config_template/settings.json` defaults; surface a one-time notice in Settings.
- Server spawn fails (port busy, spawn error): app continues; screen-control tools return a clear `ScreenControlUnavailable` error the model sees.
- PyInstaller data-file misses (asset/manifest): existing fallback-to-`base` avatar logic stays; add equivalent loud log.

## Testing

- Unit: `core/paths.py` — `is_frozen`, `config_dir`, `data_dir` with monkeypatched `sys.frozen` / `sys._MEIPASS` / HOME.
- Unit: `--serve-screen-control` dispatch (subprocess spawn called with correct argv; port-already-listening skips spawn).
- Existing 123 tests: no regressions (Qt-free core test still green; vendor import doesn't leak Qt).
- Integration (CI only, not local): the two build jobs are the real verification — first `v0.1.0` tag exercises the full pipeline.

## Rollout

1. Implement paths + vendor + entry + spec + nfpm + workflow locally.
2. Local smoke: `pyinstaller` build on Linux, run the onedir binary, confirm screen-control server spawns and avatar/GUI load from bundle.
3. Push `main`, create public repo, push tag `v0.1.0` → Actions produces deb/tar.gz/zip + Release.
4. Verify: install `.deb` on this machine, run from `/opt`, confirm self-contained (no `screen-control` repo dependency at runtime).

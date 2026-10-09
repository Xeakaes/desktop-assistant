# Packaging & GitHub Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a self-contained Desktop AI Assistant — Linux `.deb` + tar.gz, Windows `.zip` via GitHub Actions, public repo `Xeakaes/desktop-assistant`, with the screen-control SDK + server vendored into the bundle.

**Architecture:** Frozen-aware path resolution in `core/paths.py` (config → user dir when `sys.frozen`, assets → `_MEIPASS`). Screen-control client + server vendored under `vendor/sc_server/` with package renames (`core`→`sc_core`, `backends`→`sc_backends`) to avoid colliding with our own `core/`. Main entry gains `--serve-screen-control` (self-spawn as subprocess) and `--version`. PyInstaller onedir spec shared by CI matrix; nfpm builds the deb; Actions workflow builds on tag and attaches artifacts to a Release.

**Tech Stack:** Python 3.12, PySide6, PyInstaller (onedir), nfpm, GitHub Actions, Flask/mss/pyautogui/numpy (bundled server deps).

**Spec:** `docs/specs/2026-10-09-packaging-and-github-design.md`

## Global Constraints

- `core/` must never import Qt (existing test `tests/ui/test_qt_free_core.py` stays green).
- All 123 existing tests stay green after every task.
- `config/secrets.json` never enters bundle, repo, or CI logs (already gitignored).
- Dev workflow from source checkout unchanged: `python -m ui.app`, `cli.py`, `pytest`.
- License: MIT (new `LICENSE` file).
- Repo: public `desktop-assistant`.
- OCR (rapidocr) NOT bundled.
- Version: tag `vX.Y.Z` → `APP_VERSION` env → baked into binary; `core/__init__.py.__version__` default `"0.0.0"`.
- All commands from project root with `.venv/bin/` unless noted; packaging extras installed with `.venv/bin/pip install -r requirements-packaging.txt` (new file: pyinstaller, nfpm notes).

## Review Focus

1. **Vendor name collision** — vendored server's `core`/`backends` packages shadowing our `core/` in the frozen module graph. → `test_vendor_packages_renamed` (Task 2) asserts no top-level `core.backends` / `backends` modules exist under vendor and imports resolve as `vendor.sc_server.sc_core.backends`.
2. **Secrets/token files in read-only bundle** — upstream server writes `.token`/`.apikeys` beside `__file__` (fails in frozen bundle; leaks into read-only install). → vendor patch redirects via `SCREEN_CONTROL_DATA_DIR` env; `test_server_token_dir_uses_env` (Task 2).
3. **Frozen config path wrongness** — running the built exe must read/write user config dir, never `_MEIPASS/config`. → `test_config_dir_frozen_uses_home` + `test_dev_config_dir_unchanged` (Task 1).
4. **Self-spawn loop** — app spawning server that spawns app. → spawn path only from non-`--serve-screen-control` branch; `test_spawn_skipped_when_flag_present` (Task 3).
5. **CI version/artifact naming** — tag `v1.2.3` must produce `desktop-assistant_1.2.3_amd64.deb` etc., not `0.0.0`. → workflow greps `APP_VERSION` from tag; local step runs entry `--version` after build (Task 4/6).

---

### Task 1: `core/paths.py` — frozen-aware path resolution

**Files:**
- Create: `core/paths.py`
- Modify: `core/bootstrap.py:18-20` (DEFAULT_SETTINGS/DEFAULT_SECRETS via paths), `core/bootstrap.py:27-30` (default_client_factory — keep for now, Task 2 rewires import), `ui/paths.py:8-11` (delegate to core.paths), `ui/avatar_app.py:30` (ASSETS via paths)
- Test: `tests/core/test_paths.py`

**Interfaces:**
- Produces:
  - `is_frozen() -> bool` — `getattr(sys, "frozen", False)`
  - `bundle_root() -> Path` — `Path(sys._MEIPASS)` if frozen else repo root (`Path(__file__).resolve().parent.parent`)
  - `repo_root() -> Path` — always `Path(__file__).resolve().parent.parent` (source tree; used for vendor imports in dev)
  - `config_dir() -> Path` — frozen: `~/.config/desktop-assistant` (Linux) / `%APPDATA%/desktop-assistant` (nt); dev: `repo_root()/config`
  - `data_dir() -> Path` — frozen+dev: `~/.local/share/desktop-assistant` (Linux) / `%APPDATA%/desktop-assistant` (nt); mkdir parents on call
  - `assets_dir() -> Path` — `bundle_root()/assets`
- Consumes: stdlib only.

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_paths.py
import sys
from pathlib import Path

from core import paths


def test_dev_config_dir_unchanged(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert paths.config_dir() == paths.repo_root() / "config"


def test_config_dir_frozen_uses_home(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    import os
    if os.name == "nt":
        assert paths.config_dir() == tmp_path / "appdata" / "desktop-assistant"
    else:
        assert paths.config_dir() == tmp_path / ".config" / "desktop-assistant"


def test_bundle_root_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "b"), raising=False)
    assert paths.bundle_root() == tmp_path / "b"


def test_assets_dir_dev(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert paths.assets_dir() == paths.repo_root() / "assets"


def test_data_dir_creates(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    d = paths.data_dir()
    assert d.exists() and d.is_dir()
```

- [ ] **Step 2: Run to verify FAIL**

Run: `.venv/bin/pytest tests/core/test_paths.py -q` → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `core/paths.py`**

Per Interfaces above. `config_dir`/`data_dir` frozen branch: `os.name == "nt"` → `%APPDATA%/desktop-assistant`; else `Path.home()/".config"/"desktop-assistant"` and `Path.home()/".local"/"share"/"desktop-assistant"`.

- [ ] **Step 4: Rewire `core/bootstrap.py`, `ui/paths.py`, `ui/avatar_app.py`**

- `core/bootstrap.py`: `from core.paths import config_dir`; `DEFAULT_SETTINGS = config_dir() / "settings.json"`; `DEFAULT_SECRETS = config_dir() / "secrets.json"`; remove old `ROOT` constant (grep for other uses first).
- `ui/paths.py`: replace local CONFIG_DIR/SETTINGS_PATH/SECRETS_PATH with imports from `core.paths` (`SETTINGS_PATH = DEFAULT_SETTINGS` style via config_dir()). Keep `ui_json_path()` env override as-is.
- `ui/avatar_app.py`: `ASSETS = assets_dir() / "avatars"` (import from `core.paths`).
- Also check `ui/settings.py` `_list_avatars` and pack builder `avatars_root` (`Path(__file__).../assets`) — switch to `assets_dir() / "avatars"`.

- [ ] **Step 5: Full suite green**

Run: `.venv/bin/pytest tests -q` → expect 123 + 5 new = 128 passed.

- [ ] **Step 6: Commit**

```bash
git add core/paths.py core/bootstrap.py ui/paths.py ui/avatar_app.py ui/settings.py tests/core/test_paths.py
git commit -m "feat: frozen-aware path resolution for config/data/assets"
```

---

### Task 2: Vendor screen-control (SDK + server) with renames

**Files:**
- Create: `scripts/vendor_screen_control.py` (one-shot re-vendor tool; source of truth for the copy), `vendor/__init__.py`, `vendor/sc_server/__init__.py`, `vendor/sc_server/sdk.py` (from upstream `sdk/screen_control.py`), `vendor/sc_server/sc_core/{__init__.py,backends.py,errors.py}`, `vendor/sc_server/sc_backends/{__init__,linux,windows,macos,fake,forbidden,imageops,uinput}.py`, `vendor/sc_server/server.py`
- Modify: `core/bootstrap.py` `default_client_factory` (import from vendor, drop `/home/xeakaes/screen-control/sdk` sys.path hack), `requirements-packaging.txt` (new: flask, mss, pyautogui, numpy — Pillow already via ui deps? verify; pyvda win32 marker; evdev linux marker)
- Test: `tests/test_vendor.py`

**Interfaces:**
- Produces:
  - `vendor.sc_server.sdk.ScreenControl` — same class as upstream client.
  - Vendored server runnable: `python -m vendor.sc_server.server --port 8745` (imports `vendor.sc_server.sc_core.backends`).
  - Env: `SCREEN_CONTROL_DATA_DIR` — when set, server writes `.token`/`.apikeys`/`logs/` there instead of beside `__file__`; when unset, behaves like upstream (beside `__file__`).
- Consumes: Task 1 `config_dir()` (spawner sets the env in Task 3).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_vendor.py
import importlib
import os


def test_sdk_importable_from_vendor():
    mod = importlib.import_module("vendor.sc_server.sdk")
    assert hasattr(mod, "ScreenControl")


def test_vendor_packages_renamed():
    names = {m for m in __import__("sys").modules if m.startswith("vendor.sc_server")}
    assert "vendor.sc_server.sc_core.backends" in importlib.import_module(
        "vendor.sc_server.sc_core.backends"
    ).__name__
    # our own core must not gain a .backends submodule
    import core
    assert not hasattr(core, "backends")


def test_server_module_importable():
    mod = importlib.import_module("vendor.sc_server.server")
    assert hasattr(mod, "main")


def test_server_token_dir_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SCREEN_CONTROL_DATA_DIR", str(tmp_path))
    mod = importlib.import_module("vendor.sc_server.server")
    importlib.reload(mod)
    assert str(tmp_path) in mod.SESSION_TOKEN_FILE
    assert str(tmp_path) in mod.APIKEYS_FILE
```

Note: `test_server_module_importable` needs flask etc. installed — add them to `requirements-packaging.txt` and install before running (`pip install -r requirements-packaging.txt`). If flask missing locally, the test may be skipped via `pytest.importorskip("flask")`.

- [ ] **Step 2: Run to verify FAIL**

Run: `.venv/bin/pytest tests/test_vendor.py -q` → FAIL (no vendor package).

- [ ] **Step 3: Implement `scripts/vendor_screen_control.py`**

One-shot tool run manually (not in CI):
- Source: `/home/xeakaes/screen-control` (constant `UPSTREAM`).
- Copies+rewrites into `vendor/sc_server/`:
  - `sdk/screen_control.py` → `sdk.py` (no internal imports expected — verify).
  - `server.py` → `server.py` with text replacements: `from core.backends import` → `from vendor.sc_server.sc_core.backends import`; `from backends.` → `from vendor.sc_server.sc_backends.`; and token-file block replaced with env-aware version:
    ```python
    _DATA_DIR = os.environ.get("SCREEN_CONTROL_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
    SESSION_TOKEN_FILE = os.path.join(_DATA_DIR, ".token")
    APIKEYS_FILE = os.path.join(_DATA_DIR, ".apikeys")
    ```
    (locate exact upstream lines ~193-195; also `LOG_DIR` if it points beside `__file__` — redirect similarly).
  - `core/{__init__,backends,errors}.py` → `sc_core/` (rewrite internal `from backends.` → `from vendor.sc_server.sc_backends.` inside `sc_core/backends.py`).
  - `backends/*.py` → `sc_backends/` (rewrite `from core.` → `from vendor.sc_server.sc_core.` if present).
  - Skip `__pycache__`.
- Writes `vendor/__init__.py`, `vendor/sc_server/__init__.py` empty.

- [ ] **Step 4: Run the vendor script; install packaging extras**

Run: `.venv/bin/python scripts/vendor_screen_control.py` then `.venv/bin/pip install -r requirements-packaging.txt` (create the file: `flask>=3.0`, `mss>=10.0`, `pyautogui>=0.9.54`, `numpy>=1.26`, `pyvda>=0.4; sys_platform == "win32"`, `evdev>=1.3; sys_platform == "linux"`, `pyinstaller>=6.0`).

- [ ] **Step 5: Rewire `default_client_factory`**

`core/bootstrap.py`:
```python
def default_client_factory(settings, secrets):
    def factory():
        from vendor.sc_server.sdk import ScreenControl
        ...
```
Remove `sys.path` insert block. (Lazy import stays — vendor module pulls `requests` only.)

- [ ] **Step 6: Run tests to verify PASS**

Run: `.venv/bin/pytest tests -q` → expect all green + 4 new.

- [ ] **Step 7: Commit**

```bash
git add scripts/vendor_screen_control.py vendor/ core/bootstrap.py requirements-packaging.txt tests/test_vendor.py
git commit -m "feat: vendor screen-control SDK + server with package renames"
```

---

### Task 3: Entry point — `--serve-screen-control`, self-spawn, `--version`

**Files:**
- Create: `packaging/entry.py`
- Modify: `core/__init__.py` (add `__version__ = "0.0.0"`)
- Test: `tests/test_entry.py`

**Interfaces:**
- Produces:
  - `packaging.entry.serve_screen_control(argv: list[str] | None = None) -> int` — sets nothing global; calls `vendor.sc_server.server.main()` with remaining argv (server's argparse gets `--host/--port` passthrough).
  - `packaging.entry.maybe_spawn_server(settings: dict, exe_path: str | None = None) -> str | None` — returns spawned pid-str or None. Rules: if `not settings.get("screen_control", {}).get("enabled")` → None; if port 8745 already accepts TCP (`socket.create_connection(("127.0.0.1", 8745), timeout=0.3)`) → None; else `subprocess.Popen([exe_path or sys.executable, "--serve-screen-control"], env=os.environ | {"SCREEN_CONTROL_DATA_DIR": str(config_dir())}, stdout=DEVNULL, stderr=DEVNULL, start_new_session=True)` and return `str(p.pid)`.
  - `packaging.entry.main(argv: list[str] | None = None) -> int` — dispatch: `--serve-screen-control` → `serve_screen_control`; `--version` → print `os.environ.get("APP_VERSION", core.__version__)` return 0; else import `ui.app.main` and run it (which itself reads prefs for gui/avatar).
- Consumes: Task 1 `config_dir()`, Task 2 vendored server + sdk; `core.bootstrap.load_settings` for settings in spawn decision — actually `maybe_spawn_server` takes `settings: dict` so the caller (`ui.app.main` / `ui.avatar_app.App.__init__`) loads it. Wire-in: modify `ui/app.py` `main()` and `ui/avatar_app.py` `App.__init__` to call `maybe_spawn_server(load_settings(SETTINGS_PATH))` after runtime build (fail-soft: wrap in try/except, log to stderr).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_entry.py
import socket
from pathlib import Path

from packaging import entry


def test_version_flag_prints(capsys):
    assert entry.main(["--version"]) == 0
    assert "0.0.0" in capsys.readouterr().out


def test_spawn_disabled_settings(monkeypatch):
    called = []
    monkeypatch.setattr(entry.subprocess, "Popen", lambda *a, **k: called.append(a))
    assert entry.maybe_spawn_server({"screen_control": {"enabled": False}}) is None
    assert called == []


def test_spawn_skipped_when_port_open(monkeypatch):
    class FakeSock:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(entry.socket, "create_connection", lambda *a, **k: FakeSock())
    assert entry.maybe_spawn_server({"screen_control": {"enabled": True}}) is None


def test_spawn_happens_when_port_closed(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise OSError("closed")
    monkeypatch.setattr(entry.socket, "create_connection", boom)
    captured = {}
    class P:
        def __init__(self, *a, **k):
            captured["args"] = a
            captured["kwargs"] = k
        pid = 4242
    monkeypatch.setattr(entry.subprocess, "Popen", P)
    monkeypatch.setenv("SCREEN_CONTROL_DATA_DIR", str(tmp_path))
    pid = entry.maybe_spawn_server({"screen_control": {"enabled": True}})
    assert pid == "4242"
    assert "--serve-screen-control" in captured["args"][0]
    assert captured["kwargs"]["env"]["SCREEN_CONTROL_DATA_DIR"] == str(tmp_path)


def test_serve_flag_dispatches(monkeypatch):
    seen = {}
    monkeypatch.setattr(entry, "serve_screen_control", lambda argv: seen.setdefault("argv", argv) or 0)
    # route through main
    assert entry.main(["--serve-screen-control"]) == 0
```

(Adjust last test to call a thin `_dispatch(argv)` if `main` imports ui.app lazily and that's heavy — keep `main` lazy-importing `ui.app` only in the else branch so tests never touch Qt.)

- [ ] **Step 2: Run to verify FAIL**

Run: `.venv/bin/pytest tests/test_entry.py -q` → FAIL (ImportError).

- [ ] **Step 3: Implement `packaging/entry.py` + `packaging/__init__.py` (empty) + `core/__init__.py` version**

Per Interfaces. `serve_screen_control`: `sys.argv = ["screen-control-server", *rest]` then `vendor.sc_server.server.main()`.

- [ ] **Step 4: Wire `maybe_spawn_server` into `ui/app.py` and `ui/avatar_app.py`**

After runtime build (GUI: in `main()` before window; Avatar: in `App.__init__` after `build_runtime`), fail-soft call. Import path: `from packaging.entry import maybe_spawn_server` — note `packaging` name clashes with PyPA `packaging` lib if installed; **verify** `.venv` doesn't have PyPA packaging (`pip show packaging`) — if present, rename our package to `packaging_entry/` or `app_entry/`. Decision: check first; if collision, name it `app_entry/` everywhere in this task and plan references.

- [ ] **Step 5: Run tests + full suite**

Run: `.venv/bin/pytest tests -q` → green (128 + ~5 new).

- [ ] **Step 6: Commit**

```bash
git add packaging/ core/__init__.py ui/app.py ui/avatar_app.py tests/test_entry.py
git commit -m "feat: entry point with serve-screen-control, self-spawn, --version"
```

---

### Task 4: PyInstaller spec + local Linux build smoke

**Files:**
- Create: `packaging/desktop-assistant.spec`, `packaging/icon.png` (simple generated placeholder via Pillow — solid color + text "DA"), `packaging/build_linux.sh` (convenience wrapper)
- Test: manual smoke step (no pytest — binary artifact)

**Interfaces:**
- Consumes: Task 3 `packaging/entry.py` (spec's entry script), `assets/`, `vendor/`, `config/settings.json` template.
- Produces: `dist/desktop-assistant/desktop-assistant` (onedir); spec reads `APP_VERSION` env for `version` string in bundle metadata.

- [ ] **Step 1: Write `packaging/desktop-assistant.spec`**

- `Analysis(["packaging/entry.py"], datas=[("assets", "assets"), ("vendor", "vendor"), ("config/settings.json", "config_template")], hiddenimports=[flask, mss, pyautogui, PIL, numpy, PySide6 plugins + platform conditionals evdev/pyvda], ...)`
- EXE name `desktop-assistant` (+ `.exe` handled by platform), console=False, version file optional.
- COLLECT into `dist/desktop-assistant/`.

- [ ] **Step 2: Generate placeholder icon**

`.venv/bin/python -c "from PIL import Image, ImageDraw; ..." ` → `packaging/icon.png` 256×256.

- [ ] **Step 3: Local build**

Run: `APP_VERSION=0.0.0-dev bash packaging/build_linux.sh` (script: `.venv/bin/pyinstaller packaging/desktop-assistant.spec --noconfirm`). Expect `dist/desktop-assistant/desktop-assistant` exists.

- [ ] **Step 4: Smoke the binary**

Run: `dist/desktop-assistant/desktop-assistant --version` → prints `0.0.0-dev`.
Run: `timeout 10 dist/desktop-assistant/desktop-assistant --serve-screen-control` → binds :8745 (check `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8745/` returns non-000); Ctrl-C/timeout kill.
Run: `HOME=/tmp/da-smoke dist/desktop-assistant/desktop-assistant --version` again to confirm no crash from frozen config paths.

- [ ] **Step 5: Commit**

```bash
git add packaging/
git commit -m "feat: PyInstaller onedir spec with bundled assets and vendor"
```

---

### Task 5: nfpm deb + portable tar.gz

**Files:**
- Create: `packaging/nfpm.yaml`, `packaging/desktop-assistant.desktop`, extend `packaging/build_linux.sh` to also tar.gz
- Test: manual smoke

**Interfaces:**
- Consumes: Task 4 onedir output.
- Produces: `dist/desktop-assistant_<ver>_amd64.deb`, `dist/desktop-assistant_<ver>_linux_amd64.tar.gz`.

- [ ] **Step 1: Write `packaging/nfpm.yaml`**

- name: desktop-assistant; version: `${APP_VERSION}` (nfpm env expansion) or bake via sed in script; arch: amd64; maintainer; license: MIT; contents: `src: dist/desktop-assistant/ dst: /opt/desktop-assistant/`; `.desktop` → `/usr/share/applications/`; icon → `/usr/share/icons/hicolor/256x256/apps/desktop-assistant.png`; `Exec=/opt/desktop-assistant/desktop-assistant`.

- [ ] **Step 2: Extend build script** — after pyinstaller: `tar -czf dist/...tar.gz -C dist desktop-assistant`; `nfpm package --config packaging/nfpm.yaml --packager deb --target dist/`.

- [ ] **Step 3: Smoke**

Run build script; `dpkg-deb -I dist/*.deb` shows name/version; `dpkg-deb -c` shows `/opt/desktop-assistant/desktop-assistant`.

- [ ] **Step 4: Commit**

```bash
git add packaging/
git commit -m "feat: nfpm deb packaging and portable tar.gz"
```

---

### Task 6: GitHub Actions release workflow

**Files:**
- Create: `.github/workflows/release.yml`
- Test: workflow_dispatch dry run after push (Task 7); local yaml sanity via `python -c "import yaml; yaml.safe_load(open(...))"` if pyyaml available, else visual review.

- [ ] **Step 1: Write workflow**

- `on: push: tags: ["v*"]` + `workflow_dispatch`.
- Job `build-linux` (ubuntu-latest): checkout, `actions/setup-python@v5` 3.12, `pip install -r requirements.txt -r requirements-packaging.txt`, `export APP_VERSION=${GITHUB_REF_NAME#v}`, run `packaging/build_linux.sh`, upload artifacts (deb + tar.gz).
- Job `build-windows` (windows-latest): same setup, `pyinstaller packaging/desktop-assistant.spec`, `Compress-Archive -Path dist/desktop-assistant -DestinationPath dist/desktop-assistant_${{ env.APP_VERSION }}_windows_amd64.zip`, upload.
- Job `release` (needs both, `if: github.ref_type == 'tag'`): download all artifacts, `softprops/action-gh-release@v2` with files.

- [ ] **Step 2: YAML sanity check**

Run: `.venv/bin/python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/release.yml')); print('ok')"` (install pyyaml if needed, or skip with note).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: tag-triggered release build for linux deb/tar and windows zip"
```

---

### Task 7: README, LICENSE, public repo, first release

**Files:**
- Create: `README.md`, `LICENSE`
- Action: create public GitHub repo `desktop-assistant`, push `main`, tag `v0.1.0`, verify Actions run.

- [ ] **Step 1: README.md**

Sections: what it is (screenshot optional), install (deb / zip / from source), first-run (mode chooser), config locations (frozen vs dev), building from source (`pytest`, `pyinstaller`), screen-control bundled note, license MIT.

- [ ] **Step 2: LICENSE** — MIT, copyright 2026 Xeakaes.

- [ ] **Step 3: Commit**

```bash
git add README.md LICENSE
git commit -m "docs: README and MIT license"
```

- [ ] **Step 4: Create public repo + push**

- Try GitHub REST create with stored credential (parse `~/.git-credentials` for token; `POST /user/repos` name=desktop-assistant, private=false). If token lacks repo scope or file uses non-token auth → ask user to create repo on github.com and provide URL.
- `git remote add origin <url>`; `git push -u origin main`; `git tag v0.1.0`; `git push origin v0.1.0`.

- [ ] **Step 5: Verify Actions**

Poll `https://api.github.com/repos/Xeakaes/desktop-assistant/actions/runs` (or ask user to watch UI) until release job green; confirm Release `v0.1.0` has 3 assets. Note: first run may reveal hidden-import gaps — fix-forward with a patch commit + re-tag if needed.

---

## Self-review notes (resolved while writing)

- **Package name clash:** `packaging/` conflicts with PyPA `packaging` if installed in venv — Task 3 Step 4 mandates a check; fallback name `app_entry/`.
- **Server token path:** upstream lines ~193-195 + LOG_DIR — vendor script must patch all three; test pins token/apikeys.
- **`core` collision:** renames `sc_core`/`sc_backends` + absolute-import rewrites in vendor script; test asserts our `core` has no `.backends`.
- **Debian deps:** deb depends only on nothing extra (onedir bundles Python); nfpm `depends:` left empty deliberately.
- **Windows build size / AV:** onedir chosen; no signing in this milestone (spec non-goal).

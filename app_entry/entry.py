"""Main executable entry: --serve-screen-control, self-spawn, --version dispatch."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

# Bootstrap: allow running as a plain script (python app_entry/entry.py)
# where sys.path[0] is the file's directory, not the repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.paths import bundle_root, config_dir, is_frozen, repo_root


def _version_file() -> Path:
    return bundle_root() / "_version.txt"


def _bundled_version() -> str | None:
    p = _version_file()
    if p.exists():
        v = p.read_text(encoding="utf-8").strip()
        if v:
            return v
    return None


def serve_screen_control(argv: list[str] | None = None) -> int:
    os.environ.setdefault("SCREEN_CONTROL_DATA_DIR", str(config_dir()))
    from vendor.sc_server.server import main as server_main

    rest = argv if argv is not None else sys.argv[1:]
    rest = [a for a in rest if a != "--serve-screen-control"]
    sys.argv = ["screen-control-server", *rest]
    server_main()
    return 0


def maybe_spawn_server(settings: dict, exe_path: str | None = None) -> str | None:
    sc = settings.get("screen_control") or {}
    if not sc.get("enabled"):
        return None
    host = sc.get("host", "127.0.0.1")
    port = int(sc.get("port", 8745))
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return None  # already listening
    except OSError:
        pass

    env = {**os.environ, "SCREEN_CONTROL_DATA_DIR": str(config_dir())}
    if is_frozen():
        cmd = [
            exe_path or sys.executable,
            "--serve-screen-control",
            "--host",
            host,
            "--port",
            str(port),
        ]
        kwargs: dict = {}
    else:
        cmd = [
            sys.executable,
            "-m",
            "vendor.sc_server.server",
            "--host",
            host,
            "--port",
            str(port),
        ]
        kwargs = {"cwd": str(repo_root())}
    try:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            **kwargs,
        )
    except OSError:
        return None
    return str(proc.pid)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--serve-screen-control" in args:
        return serve_screen_control(args)
    if "--version" in args:
        import core

        print(
            os.environ.get("APP_VERSION")
            or _bundled_version()
            or getattr(core, "__version__", "0.0.0")
        )
        return 0
    from ui.app import main as ui_main

    return ui_main()


if __name__ == "__main__":
    sys.exit(main())

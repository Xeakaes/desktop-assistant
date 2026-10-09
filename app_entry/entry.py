"""Main executable entry: --serve-screen-control, self-spawn, --version dispatch."""

from __future__ import annotations

import os
import socket
import subprocess
import sys


def serve_screen_control(argv: list[str] | None = None) -> int:
    from vendor.sc_server.server import main as server_main

    rest = argv if argv is not None else sys.argv[1:]
    # server.main() reads sys.argv via argparse; strip our flag
    rest = [a for a in rest if a != "--serve-screen-control"]
    sys.argv = ["screen-control-server", *rest]
    server_main()
    return 0


def maybe_spawn_server(settings: dict, exe_path: str | None = None) -> str | None:
    sc = settings.get("screen_control") or {}
    if not sc.get("enabled"):
        return None
    port = int(sc.get("port", 8745))
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return None  # already listening
    except OSError:
        pass
    from core.paths import config_dir

    env = {**os.environ, "SCREEN_CONTROL_DATA_DIR": str(config_dir())}
    try:
        proc = subprocess.Popen(
            [exe_path or sys.executable, "--serve-screen-control"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
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

        print(os.environ.get("APP_VERSION", getattr(core, "__version__", "0.0.0")))
        return 0
    from ui.app import main as ui_main

    return ui_main()


if __name__ == "__main__":
    sys.exit(main())

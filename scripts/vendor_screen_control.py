#!/usr/bin/env python3
"""One-shot vendor tool: copy screen-control SDK+server into vendor/sc_server/ with renames.

Run manually when upstream /home/xeakaes/screen-control changes:
    .venv/bin/python scripts/vendor_screen_control.py

Renames (to avoid shadowing our own core/):
    core    -> sc_core
    backends -> sc_backends
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

UPSTREAM = Path("/home/xeakaes/screen-control")
REPO = Path(__file__).resolve().parent.parent
DEST = REPO / "vendor" / "sc_server"


def _rewrite_imports(src: str) -> str:
    """Rewrite absolute imports of upstream packages to vendor.sc_server namespace."""
    src = re.sub(
        r"^from core\.backends import",
        "from vendor.sc_server.sc_core.backends import",
        src,
        flags=re.M,
    )
    src = re.sub(
        r"^from core\.errors import",
        "from vendor.sc_server.sc_core.errors import",
        src,
        flags=re.M,
    )
    src = re.sub(
        r"^from core\.",
        "from vendor.sc_server.sc_core.",
        src,
        flags=re.M,
    )
    src = re.sub(
        r"^(\s*)from backends import",
        r"\1from vendor.sc_server.sc_backends import",
        src,
        flags=re.M,
    )
    src = re.sub(
        r"^(\s*)from backends\.",
        r"\1from vendor.sc_server.sc_backends.",
        src,
        flags=re.M,
    )
    src = re.sub(
        r"^(\s*)from core\.",
        r"\1from vendor.sc_server.sc_core.",
        src,
        flags=re.M,
    )
    return src


def _patch_server_token_paths(src: str) -> str:
    """Redirect .token/.apikeys/logs to SCREEN_CONTROL_DATA_DIR when set."""
    src = src.replace(
        'SESSION_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".token")',
        '_DATA_DIR = os.environ.get("SCREEN_CONTROL_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))\n'
        'SESSION_TOKEN_FILE = os.path.join(_DATA_DIR, ".token")',
    )
    src = src.replace(
        'APIKEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".apikeys")',
        'APIKEYS_FILE = os.path.join(_DATA_DIR, ".apikeys")',
    )
    src = src.replace(
        'LOG_DIR = Path(__file__).parent / "logs"',
        'LOG_DIR = Path(os.environ.get("SCREEN_CONTROL_DATA_DIR") or Path(__file__).parent) / "logs"',
    )
    # LOG_DIR.mkdir runs at import; ensure parent exists
    src = src.replace(
        "LOG_DIR.mkdir(exist_ok=True)",
        "LOG_DIR.mkdir(parents=True, exist_ok=True)",
    )
    return src


def _copy_py(src: Path, dest: Path, extra_patch=None) -> None:
    text = src.read_text(encoding="utf-8")
    text = _rewrite_imports(text)
    if extra_patch:
        text = extra_patch(text)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def _verify_rewrites() -> bool:
    """Fail loudly if any un-rewritten import survived."""
    ok = True
    for f in DEST.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        if re.search(r"^from core[.\s]", text, re.M) or re.search(
            r"^import core\b", text, re.M
        ):
            print(f"REWRITE INCOMPLETE: {f} still imports 'core'", file=sys.stderr)
            ok = False
        if re.search(r"^from backends[.\s]", text, re.M) or re.search(
            r"^import backends\b", text, re.M
        ):
            print(f"REWRITE INCOMPLETE: {f} still imports 'backends'", file=sys.stderr)
            ok = False
    server = (DEST / "server.py").read_text(encoding="utf-8")
    if "_DATA_DIR" not in server or "SCREEN_CONTROL_DATA_DIR" not in server:
        print("REWRITE INCOMPLETE: server.py token path patch missing", file=sys.stderr)
        ok = False
    return ok


def main() -> int:
    if not UPSTREAM.is_dir():
        print(f"error: upstream not found: {UPSTREAM}", file=sys.stderr)
        return 1
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    (REPO / "vendor" / "__init__.py").write_text("")
    (DEST / "__init__.py").write_text("")

    # SDK client — no internal project imports
    _copy_py(UPSTREAM / "sdk" / "screen_control.py", DEST / "sdk.py")

    # server
    _copy_py(
        UPSTREAM / "server.py",
        DEST / "server.py",
        extra_patch=_patch_server_token_paths,
    )

    # core -> sc_core
    for f in (UPSTREAM / "core").glob("*.py"):
        _copy_py(f, DEST / "sc_core" / f.name)
    # backends -> sc_backends
    for f in (UPSTREAM / "backends").glob("*.py"):
        _copy_py(f, DEST / "sc_backends" / f.name)

    if not _verify_rewrites():
        return 1

    print(f"vendored -> {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

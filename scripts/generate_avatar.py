#!/usr/bin/env python3
"""CLI wrapper around ui.avatar.pack.build_pack (spec §8)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.avatar.pack import PackError, build_pack, sanitize_pack_name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default=None)
    args = ap.parse_args()
    out = Path(args.out)
    name = args.name or out.name
    try:
        build_pack(Path(args.source), out, sanitize_pack_name(name))
    except PackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote pack -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

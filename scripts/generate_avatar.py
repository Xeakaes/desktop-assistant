#!/usr/bin/env python3
"""Offline: build assets/avatars/<name>/ frames + manifest from a source JPEG.

Background removal: flood-fill from borders (tolerance 48), then keep only
the largest remaining opaque connected component (drops palette strip and
watermark). Frames use integer-pixel transforms — pixel art stays crisp.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

from PIL import Image

TOLERANCE = 48
PAD = 8
TARGET_H = 192

STATE_TRANSFORMS: dict[str, dict] = {
    "idle": {"dy": [0, -2, 0, 2], "fps": 6, "loop": True},
    "thinking": {"dx": [0, 3, 0, -3], "fps": 4, "loop": True},
    "working": {"dy": [0, -3, -5, -3, 0, 3], "fps": 10, "loop": True},
    "speaking": {"dy": [0, -4, 0, -2], "fps": 8, "loop": True},
    "error": {"dy": [0, 0, 0], "tint": [True, False, True], "fps": 5, "loop": False},
}


def _near(c1, c2, tol: int) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(c1[:3], c2[:3]))


def strip_background(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    seeds = []
    for x in range(w):
        seeds.append((x, 0))
        seeds.append((x, h - 1))
    for y in range(h):
        seeds.append((0, y))
        seeds.append((w - 1, y))
    bg = px[0, 0]
    seen = set()
    q = deque(seeds)
    while q:
        x, y = q.popleft()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        seen.add((x, y))
        if _near(px[x, y], bg, TOLERANCE):
            px[x, y] = (0, 0, 0, 0)
            q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return img


def keep_largest_component(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    visited = set()
    best: list[tuple[int, int]] = []
    for sy in range(h):
        for sx in range(w):
            if (sx, sy) in visited or px[sx, sy][3] == 0:
                continue
            comp: list[tuple[int, int]] = []
            q = deque([(sx, sy)])
            while q:
                x, y = q.popleft()
                if (x, y) in visited or not (0 <= x < w and 0 <= y < h):
                    continue
                visited.add((x, y))
                if px[x, y][3] == 0:
                    continue
                comp.append((x, y))
                q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
            if len(comp) > len(best):
                best = comp
    keep = set(best)
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 0 and (x, y) not in keep:
                px[x, y] = (0, 0, 0, 0)
    return img


def crop_pad_resize(img: Image.Image, target_h: int = TARGET_H) -> Image.Image:
    bbox = img.getbbox()
    if bbox is None:
        raise SystemExit("source image is empty after background removal")
    img = img.crop(bbox)
    w, h = img.size
    canvas = Image.new("RGBA", (w + 2 * PAD, h + 2 * PAD), (0, 0, 0, 0))
    canvas.paste(img, (PAD, PAD))
    scale = target_h / canvas.height
    new_w = max(1, round(canvas.width * scale))
    return canvas.resize((new_w, target_h), Image.NEAREST)


def transform(base: Image.Image, dx: int = 0, dy: int = 0, tint: bool = False) -> Image.Image:
    out = Image.new("RGBA", base.size, (0, 0, 0, 0))
    out.paste(base, (dx, dy), base)
    if tint:
        px = out.load()
        for y in range(out.height):
            for x in range(out.width):
                r, g, b, a = px[x, y]
                if a > 0:
                    px[x, y] = (min(255, r + 102), int(g * 0.6), int(b * 0.6), a)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    out = Path(args.out)
    name = args.name or out.name
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    base = Image.open(args.source)
    base = keep_largest_component(strip_background(base))
    base = crop_pad_resize(base)

    manifest: dict = {"name": name, "states": {}}
    for state, cfg in STATE_TRANSFORMS.items():
        n = max(len(cfg.get("dx") or [0]), len(cfg.get("dy") or [0]), len(cfg.get("tint") or [False]))
        rels = []
        for i in range(n):
            dx = (cfg.get("dx") or [0] * n)[i]
            dy = (cfg.get("dy") or [0] * n)[i]
            tint = (cfg.get("tint") or [False] * n)[i]
            frame = transform(base, dx=dx, dy=dy, tint=tint)
            rel = f"frames/{state}_{i:02d}.png"
            frame.save(out / rel)
            rels.append(rel)
        manifest["states"][state] = {
            "frames": rels,
            "fps": cfg["fps"],
            "loop": cfg["loop"],
        }

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    total = sum(len(s["frames"]) for s in manifest["states"].values())
    print(f"wrote {total} frames + manifest.json -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

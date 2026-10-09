"""Pure-Python loader for avatar manifest.json (spec §4.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED_STATES = ("idle", "thinking", "working", "speaking", "error")


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class StateAnim:
    frames: tuple[str, ...]
    fps: float
    loop: bool


def load_manifest(path: Path) -> dict[str, StateAnim]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read manifest: {exc}") from exc
    states = data.get("states")
    if not isinstance(states, dict):
        raise ManifestError("manifest must contain a 'states' object")
    base = path.parent
    out: dict[str, StateAnim] = {}
    for name in REQUIRED_STATES:
        if name not in states:
            raise ManifestError(f"missing state: {name}")
        raw = states[name]
        frames = raw.get("frames") or []
        if not frames:
            raise ManifestError(f"state {name}: frames must be non-empty")
        fps = raw.get("fps", 0)
        try:
            fps = float(fps)
        except (TypeError, ValueError):
            fps = 0.0
        if fps <= 0:
            raise ManifestError(f"state {name}: fps must be > 0")
        out[name] = StateAnim(
            frames=tuple(str(base / f) for f in frames),
            fps=fps,
            loop=bool(raw.get("loop", True)),
        )
    return out

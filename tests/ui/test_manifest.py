from pathlib import Path

import pytest

from ui.avatar.manifest import ManifestError, load_manifest

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "avatars" / "base"
REQUIRED = {"idle", "thinking", "working", "speaking", "error"}


def _manifest(states: dict) -> str:
    import json

    return json.dumps({"name": "x", "states": states})


def _state(fps: float = 6.0) -> dict:
    return {"frames": ["f.png"], "fps": fps, "loop": True}


def test_real_manifest_loads():
    states = load_manifest(ASSETS / "manifest.json")
    assert set(states) == REQUIRED
    assert all(s.frames and s.fps > 0 for s in states.values())
    assert all((ASSETS / f).exists() for s in states.values() for f in s.frames)


def test_manifest_missing_state_raises(tmp_path):
    (tmp_path / "manifest.json").write_text(_manifest({}))
    with pytest.raises(ManifestError, match="missing state"):
        load_manifest(tmp_path / "manifest.json")


def test_manifest_empty_frames_raises(tmp_path):
    states = {name: _state() for name in REQUIRED}
    states["idle"] = {"frames": [], "fps": 6, "loop": True}
    (tmp_path / "manifest.json").write_text(_manifest(states))
    with pytest.raises(ManifestError, match="frames"):
        load_manifest(tmp_path / "manifest.json")


def test_manifest_bad_fps_raises(tmp_path):
    states = {name: _state() for name in REQUIRED}
    states["idle"] = _state(fps=0)
    (tmp_path / "manifest.json").write_text(_manifest(states))
    with pytest.raises(ManifestError, match="fps"):
        load_manifest(tmp_path / "manifest.json")

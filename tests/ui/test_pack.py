import json
from pathlib import Path

import pytest

from ui.avatar.pack import PackError, build_pack, sanitize_pack_name

MIKU = Path("/home/xeakaes/İndirilenler/Miku pixel art!.jpeg")
REQUIRED = {"idle", "thinking", "working", "speaking", "error"}


def test_build_pack_produces_five_states(tmp_path):
    if not MIKU.exists():
        pytest.skip("source image not available")
    out = tmp_path / "miku"
    result = build_pack(MIKU, out, "miku")
    assert result == out
    manifest = json.loads((out / "manifest.json").read_text())
    assert set(manifest["states"]) == REQUIRED
    for state in manifest["states"].values():
        for rel in state["frames"]:
            assert (out / rel).exists()


def test_build_pack_existing_dir_raises(tmp_path):
    out = tmp_path / "x"
    out.mkdir()
    with pytest.raises(PackError, match="exists"):
        build_pack(MIKU if MIKU.exists() else tmp_path, out, "x")


def test_build_pack_corrupt_image_raises(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image at all")
    with pytest.raises(PackError):
        build_pack(bad, tmp_path / "out", "badpack")


def test_sanitize_pack_name():
    assert sanitize_pack_name("Miku Pixel Art!") == "miku_pixel_art"
    assert sanitize_pack_name("  Hello--World  ") == "hello_world"
    with pytest.raises(PackError):
        sanitize_pack_name("!!!")

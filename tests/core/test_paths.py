import os
import sys

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
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: tmp_path))
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
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: tmp_path))
    d = paths.data_dir()
    assert d.exists() and d.is_dir()
    if os.name != "nt":
        assert d == tmp_path / ".local" / "share" / "desktop-assistant"

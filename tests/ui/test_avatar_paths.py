"""Avatar pack location tests: writable user dir + merged listing (Task 3)."""

from __future__ import annotations

import json


def test_user_avatars_dir_under_config(tmp_path, monkeypatch):
    monkeypatch.setattr("core.paths.config_dir", lambda: tmp_path)
    from core.paths import user_avatars_dir

    d = user_avatars_dir()
    assert d == tmp_path / "avatars"
    assert d.is_dir()  # created on demand


def test_list_avatars_merges_bundle_and_user(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from core.paths import assets_dir, config_dir
    from ui.settings import SettingsWindow

    app = QApplication.instance() or QApplication([])
    # Fake bundle with base; fake user dir with teto.
    bundle = tmp_path / "bundle_assets" / "avatars"
    (bundle / "base" / "frames").mkdir(parents=True)
    (bundle / "base" / "manifest.json").write_text("{}")
    user = tmp_path / "cfg" / "avatars"
    (user / "teto" / "frames").mkdir(parents=True)
    (user / "teto" / "manifest.json").write_text("{}")

    monkeypatch.setattr("core.paths.assets_dir", lambda: tmp_path / "bundle_assets")
    monkeypatch.setattr("core.paths.config_dir", lambda: tmp_path / "cfg")

    settings = tmp_path / "settings.json"
    settings.write_text('{"provider": {"type": "ollama", "url": "", "model": "x"}}')
    secrets = tmp_path / "secrets.json"
    secrets.write_text("{}")
    ui_json = tmp_path / "ui.json"
    win = SettingsWindow(settings, secrets, ui_json)
    names = win._list_avatars()
    assert "base" in names
    assert "teto" in names
    win.hide()
    win.deleteLater()


def test_build_pack_writes_to_user_dir(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from ui.settings import SettingsWindow

    app = QApplication.instance() or QApplication([])
    bundle = tmp_path / "bundle_assets" / "avatars"
    (bundle / "base" / "frames").mkdir(parents=True)
    (bundle / "base" / "manifest.json").write_text("{}")
    user = tmp_path / "cfg" / "avatars"

    monkeypatch.setattr("core.paths.assets_dir", lambda: tmp_path / "bundle_assets")
    monkeypatch.setattr("core.paths.config_dir", lambda: tmp_path / "cfg")

    # Make a tiny real image with a distinct foreground (not a flat color,
    # which strip_background would erase entirely).
    from PIL import Image

    src = tmp_path / "photo.png"
    img = Image.new("RGB", (64, 64), (255, 255, 255))  # white background
    for x in range(20, 44):
        for y in range(20, 44):
            img.putpixel((x, y), (200, 30, 30))  # red foreground block
    img.save(src)

    settings = tmp_path / "settings.json"
    settings.write_text('{"provider": {"type": "ollama", "url": "", "model": "x"}}')
    secrets = tmp_path / "secrets.json"
    secrets.write_text("{}")
    ui_json = tmp_path / "ui.json"
    win = SettingsWindow(settings, secrets, ui_json)
    win._pack_path.setText(str(src))
    win._pack_name.setText("myhero")
    win._build_pack()
    # Build runs on a QThread now — wait for it to finish.
    assert win._pack_worker is not None
    assert win._pack_worker.wait(10000), "pack build thread did not finish"
    # Pack must land in the user dir, not the bundle.
    assert (user / "myhero" / "manifest.json").is_file()
    assert not (bundle / "myhero").exists()
    win.hide()
    win.deleteLater()


def test_delete_pack_only_touches_user_dir(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ui.settings import SettingsWindow

    app = QApplication.instance() or QApplication([])
    bundle = tmp_path / "bundle_assets" / "avatars"
    (bundle / "base" / "frames").mkdir(parents=True)
    (bundle / "base" / "manifest.json").write_text(json.dumps({"name": "base", "states": {}}))
    user = tmp_path / "cfg" / "avatars"
    (user / "teto" / "frames").mkdir(parents=True)
    (user / "teto" / "manifest.json").write_text(json.dumps({"name": "teto", "states": {}}))

    monkeypatch.setattr("core.paths.assets_dir", lambda: tmp_path / "bundle_assets")
    monkeypatch.setattr("core.paths.config_dir", lambda: tmp_path / "cfg")
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )

    settings = tmp_path / "settings.json"
    settings.write_text('{"provider": {"type": "ollama", "url": "", "model": "x"}}')
    secrets = tmp_path / "secrets.json"
    secrets.write_text("{}")
    ui_json = tmp_path / "ui.json"
    win = SettingsWindow(settings, secrets, ui_json)
    win.load()
    idx = win._avatar.findText("teto")
    assert idx >= 0
    win._avatar.setCurrentIndex(idx)
    win._delete_pack()
    assert not (user / "teto").exists()
    assert (bundle / "base").exists()
    win.hide()
    win.deleteLater()

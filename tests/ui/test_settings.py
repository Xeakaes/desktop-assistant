from pathlib import Path

from ui.settings import merge_permissions


def test_merge_permissions_overrides_defaults():
    merged = merge_permissions({"*": "ask"}, "allow", {"screenshot": "deny"})
    assert merged["*"] == "allow"
    assert merged["screenshot"] == "deny"


def test_settings_window_load_and_save(tmp_path):
    from PySide6.QtWidgets import QApplication

    from ui.settings import SettingsWindow

    app = QApplication.instance() or QApplication([])
    settings = tmp_path / "settings.json"
    settings.write_text(
        '{"provider": {"type": "ollama", "url": "", "model": "x"},'
        ' "screen_control": {"enabled": true, "host": "127.0.0.1", "port": 8745},'
        ' "permissions": {"*": "ask"}, "avatar": "base"}'
    )
    secrets = tmp_path / "secrets.json"
    secrets.write_text('{"screen_control_api_key": "k", "api_key": ""}')
    ui_json = tmp_path / "ui.json"
    win = SettingsWindow(settings, secrets, ui_json)
    win.load()
    assert win._provider_type.currentText() == "ollama"
    assert win._provider_url.text() == ""
    win._provider_url.setText("http://localhost:11434")
    win.save()
    import json

    data = json.loads(settings.read_text())
    assert data["provider"]["url"] == "http://localhost:11434"
    win.hide()
    win.deleteLater()


def _make_settings_files(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        '{"provider": {"type": "ollama", "url": "", "model": "x"},'
        ' "screen_control": {"enabled": true, "host": "127.0.0.1", "port": 8745},'
        ' "permissions": {"*": "ask"}, "avatar": "base"}'
    )
    secrets = tmp_path / "secrets.json"
    secrets.write_text('{"screen_control_api_key": "k", "api_key": ""}')
    ui_json = tmp_path / "ui.json"
    return settings, secrets, ui_json


def test_delete_pack_removes_dir_and_refreshes(tmp_path, monkeypatch):
    import json

    from PySide6.QtWidgets import QApplication, QMessageBox

    from ui.settings import SettingsWindow

    app = QApplication.instance() or QApplication([])
    settings, secrets, ui_json = _make_settings_files(tmp_path)

    # Fake an avatars root with a deletable pack and the built-in base.
    # _delete_pack uses user_avatars_dir() -> config_dir()/avatars.
    cfg = tmp_path / "cfg"
    avatars = cfg / "avatars"
    pack = avatars / "teto"
    (pack / "frames").mkdir(parents=True)
    (pack / "manifest.json").write_text(json.dumps({"name": "teto", "states": {}}))
    base = avatars / "base"
    (base / "frames").mkdir(parents=True)
    (base / "manifest.json").write_text(json.dumps({"name": "base", "states": {}}))

    # Empty bundle so _list_avatars does not pick up real on-disk packs.
    bundle = tmp_path / "bundle_assets"
    (bundle / "avatars").mkdir(parents=True)
    monkeypatch.setattr("core.paths.assets_dir", lambda: bundle)
    monkeypatch.setattr("core.paths.config_dir", lambda: cfg)
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )

    win = SettingsWindow(settings, secrets, ui_json)
    win.load()
    # Point the combo at the pack we want to delete.
    idx = win._avatar.findText("teto")
    assert idx >= 0, f"teto not in combo: {win._avatar.count()}"
    win._avatar.setCurrentIndex(idx)
    win._delete_pack()
    assert not pack.exists()
    assert base.exists()  # built-in never deleted
    # Combo no longer lists the deleted pack.
    assert win._avatar.findText("teto") == -1
    win.hide()
    win.deleteLater()


def test_delete_pack_refuses_base(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from core.paths import assets_dir
    from ui.settings import SettingsWindow

    app = QApplication.instance() or QApplication([])
    settings, secrets, ui_json = _make_settings_files(tmp_path)
    avatars = tmp_path / "avatars"
    base = avatars / "base"
    (base / "frames").mkdir(parents=True)
    (base / "manifest.json").write_text('{"name": "base", "states": {}}')

    monkeypatch.setattr("core.paths.assets_dir", lambda: tmp_path)

    win = SettingsWindow(settings, secrets, ui_json)
    win.load()
    win._avatar.setCurrentIndex(win._avatar.findText("base"))
    win._delete_pack()
    assert base.exists()  # still there
    win.hide()
    win.deleteLater()

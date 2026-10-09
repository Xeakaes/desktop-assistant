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

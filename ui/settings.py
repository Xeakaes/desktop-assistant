"""Settings window (spec §4.4): provider, screen-control, permissions, avatar."""

from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

PROVIDER_TYPES = ["ollama", "openai_compat", "nvidia", "groq", "google", "nararouter"]
PERMISSION_LEVELS = ["allow", "ask", "deny"]
KNOWN_TOOLS = [
    "screenshot",
    "ocr_screen",
    "mouse",
    "keyboard",
    "list_windows",
    "focus_window",
]
PROVIDER_KEY_SECRETS = {
    "openai_compat": "api_key",
    "nvidia": "nvidia_api_key",
    "groq": "groq_api_key",
    "google": "google_api_key",
    "nararouter": "nararouter_api_key",
}


def merge_permissions(existing: dict, default: str, per_tool: dict) -> dict:
    """Update only the levels the UI shows; keep hand-edited tool entries."""
    merged = dict(existing)
    merged["*"] = default
    merged.update(per_tool)
    return merged


class SettingsWindow(QWidget):
    def __init__(self, settings_path: Path, secrets_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ayarlar — Desktop Assistant")
        self.setMinimumWidth(420)
        # Closing the settings window must NOT quit the whole app (WA_QuitOnClose
        # is true by default for top-level widgets; the avatar is a Tool window
        # and does not keep the app alive).
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self._settings_path = settings_path
        self._secrets_path = secrets_path

        self._provider_type = QComboBox(self)
        self._provider_type.addItems(PROVIDER_TYPES)
        self._provider_url = QLineEdit(self)
        self._provider_model = QLineEdit(self)
        self._provider_key = QLineEdit(self)
        self._provider_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._sc_host = QLineEdit(self)
        self._sc_port = QSpinBox(self)
        self._sc_port.setRange(1, 65535)
        self._sc_key = QLineEdit(self)
        self._sc_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._perm_default = QComboBox(self)
        self._perm_default.addItems(PERMISSION_LEVELS)
        self._perm_tools = {}
        self._avatar = QComboBox(self)

        form = QFormLayout()
        form.addRow("Sağlayıcı", self._provider_type)
        form.addRow("URL (boş = varsayılan)", self._provider_url)
        form.addRow("Model", self._provider_model)
        form.addRow("API anahtarı", self._provider_key)
        form.addRow("SC host", self._sc_host)
        form.addRow("SC port", self._sc_port)
        form.addRow("SC anahtarı", self._sc_key)
        form.addRow("İzin (*)", self._perm_default)
        for tool in KNOWN_TOOLS:
            combo = QComboBox(self)
            combo.addItems(PERMISSION_LEVELS)
            self._perm_tools[tool] = combo
            form.addRow(f"İzin ({tool})", combo)
        form.addRow("Avatar", self._avatar)

        self._status = QLabel("", self)
        save_btn = QPushButton("Kaydet", self)
        save_btn.clicked.connect(self.save)
        close_btn = QPushButton("Kapat", self)
        close_btn.clicked.connect(self.close)
        buttons = QHBoxLayout()
        buttons.addWidget(save_btn)
        buttons.addWidget(close_btn)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._status)
        layout.addLayout(buttons)

        self.load()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.hide()
        event.ignore()

    def load(self) -> None:
        settings = self._read(self._settings_path)
        secrets = self._read(self._secrets_path)
        provider = settings.get("provider") or {}
        idx = self._provider_type.findText(provider.get("type", "ollama"))
        self._provider_type.setCurrentIndex(max(0, idx))
        self._provider_url.setText(provider.get("url", ""))
        self._provider_model.setText(provider.get("model", ""))
        key_name = PROVIDER_KEY_SECRETS.get(self._provider_type.currentText(), "api_key")
        self._provider_key.setText(str(secrets.get(key_name, "")))
        sc = settings.get("screen_control") or {}
        self._sc_host.setText(sc.get("host", "127.0.0.1"))
        self._sc_port.setValue(int(sc.get("port", 8745)))
        self._sc_key.setText(secrets.get("screen_control_api_key", ""))
        perms = settings.get("permissions") or {}
        idx = self._perm_default.findText(perms.get("*", "ask"))
        self._perm_default.setCurrentIndex(max(0, idx))
        for tool, combo in self._perm_tools.items():
            idx = combo.findText(perms.get(tool, "ask"))
            combo.setCurrentIndex(max(0, idx))
        self._avatar.clear()
        self._avatar.addItems(self._list_avatars())
        idx = self._avatar.findText(settings.get("avatar", "base"))
        if idx >= 0:
            self._avatar.setCurrentIndex(idx)
        self._status.setText("")

    def save(self) -> None:
        settings = self._read(self._settings_path)
        secrets = self._read(self._secrets_path)
        ptype = self._provider_type.currentText()
        provider = {"type": ptype, "model": self._provider_model.text().strip()}
        url = self._provider_url.text().strip()
        if url:
            provider["url"] = url
        settings["provider"] = provider
        sc = settings.get("screen_control") or {"enabled": True}
        sc["host"] = self._sc_host.text().strip() or "127.0.0.1"
        sc["port"] = int(self._sc_port.value())
        settings["screen_control"] = sc
        per_tool = {tool: combo.currentText() for tool, combo in self._perm_tools.items()}
        settings["permissions"] = merge_permissions(
            settings.get("permissions") or {},
            self._perm_default.currentText(),
            per_tool,
        )
        settings["avatar"] = self._avatar.currentText() or "base"
        key_name = PROVIDER_KEY_SECRETS.get(ptype, "api_key")
        key_value = self._provider_key.text().strip()
        if key_value:
            secrets[key_name] = key_value
        secrets["screen_control_api_key"] = self._sc_key.text().strip()
        self._write(self._settings_path, settings)
        self._write(self._secrets_path, secrets, mode=0o600)
        self._status.setText("Kaydedildi — sağlayıcı/izinler için yeniden başlatın")

    def _list_avatars(self) -> list:
        root = Path(__file__).resolve().parent.parent / "assets" / "avatars"
        if not root.is_dir():
            return ["base"]
        return sorted(p.name for p in root.iterdir() if p.is_dir()) or ["base"]

    @staticmethod
    def _read(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _write(path: Path, data: dict, mode=None) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode if mode is not None else 0o644)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        if mode is not None:
            os.chmod(path, mode)

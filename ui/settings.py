"""Settings window (spec §4.4): provider, screen-control, permissions, avatar."""

from __future__ import annotations

import json
import os
from pathlib import Path

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
KNOWN_TOOLS = ["screenshot", "list_windows", "ocr"]


class SettingsWindow(QWidget):
    def __init__(
        self,
        settings_path: Path,
        secrets_path: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ayarlar — Desktop Assistant")
        self.setMinimumWidth(420)
        self._settings_path = settings_path
        self._secrets_path = secrets_path

        self._provider_type = QComboBox(self)
        self._provider_type.addItems(PROVIDER_TYPES)
        self._provider_url = QLineEdit(self)
        self._provider_model = QLineEdit(self)
        self._sc_host = QLineEdit(self)
        self._sc_port = QSpinBox(self)
        self._sc_port.setRange(1, 65535)
        self._sc_key = QLineEdit(self)
        self._sc_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._perm_default = QComboBox(self)
        self._perm_default.addItems(PERMISSION_LEVELS)
        self._perm_tools: dict[str, QComboBox] = {}
        self._avatar = QComboBox(self)

        form = QFormLayout()
        form.addRow("Sağlayıcı", self._provider_type)
        form.addRow("URL", self._provider_url)
        form.addRow("Model", self._provider_model)
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

    def load(self) -> None:
        settings = self._read(self._settings_path)
        secrets = self._read(self._secrets_path)
        provider = settings.get("provider") or {}
        idx = self._provider_type.findText(provider.get("type", "ollama"))
        self._provider_type.setCurrentIndex(max(0, idx))
        self._provider_url.setText(provider.get("url", ""))
        self._provider_model.setText(provider.get("model", ""))
        sc = settings.get("screen_control") or {}
        self._sc_host.setText(sc.get("host", "127.0.0.1"))
        self._sc_port.setValue(int(sc.get("port", 8745)))
        self._sc_key.setText(secrets.get("screen_control_api_key", ""))
        perms = settings.get("permissions") or {}
        idx = self._perm_default.findText(perms.get("*", "deny"))
        self._perm_default.setCurrentIndex(max(0, idx))
        for tool, combo in self._perm_tools.items():
            idx = combo.findText(perms.get(tool, "deny"))
            combo.setCurrentIndex(max(0, idx))
        self._avatar.clear()
        avatars = self._list_avatars()
        self._avatar.addItems(avatars)
        current = settings.get("avatar", "base")
        idx = self._avatar.findText(current)
        self._avatar.setCurrentIndex(max(0, idx))
        self._status.setText("")

    def save(self) -> None:
        settings = self._read(self._settings_path)
        secrets = self._read(self._secrets_path)
        settings["provider"] = {
            "type": self._provider_type.currentText(),
            "url": self._provider_url.text().strip(),
            "model": self._provider_model.text().strip(),
        }
        sc = settings.get("screen_control") or {"enabled": True}
        sc["host"] = self._sc_host.text().strip() or "127.0.0.1"
        sc["port"] = int(self._sc_port.value())
        settings["screen_control"] = sc
        perms = {"*": self._perm_default.currentText()}
        for tool, combo in self._perm_tools.items():
            perms[tool] = combo.currentText()
        settings["permissions"] = perms
        settings["avatar"] = self._avatar.currentText() or "base"
        secrets["screen_control_api_key"] = self._sc_key.text().strip()
        self._write(self._settings_path, settings)
        self._write(self._secrets_path, secrets, mode=0o600)
        self._status.setText("Kaydedildi")

    def _list_avatars(self) -> list[str]:
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
    def _write(path: Path, data: dict, mode: int | None = None) -> None:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        if mode is not None:
            os.chmod(path, mode)

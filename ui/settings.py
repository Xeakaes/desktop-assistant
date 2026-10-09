"""Settings window v2: general (lang/theme/mode), provider, screen, perms, packs."""

from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.avatar.pack import PackError, build_pack, sanitize_pack_name
from ui.i18n import i18n
from ui.prefs import THEMES, load_prefs, save_prefs, UiPrefs
from ui.theme import REQUIRED_OBJECTNAMES  # noqa: F401  (theme presence check)

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
    merged = dict(existing)
    merged["*"] = default
    merged.update(per_tool)
    return merged


class SettingsWindow(QWidget):
    language_changed = Signal(str)
    theme_changed = Signal(str)

    def __init__(
        self,
        settings_path: Path,
        secrets_path: Path,
        ui_json_path: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settings_win")
        self.setMinimumWidth(460)
        self._settings_path = settings_path
        self._secrets_path = secrets_path
        self._ui_json_path = ui_json_path or (
            settings_path.parent / "ui.json"
        )
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

        self._lang = QComboBox(self)
        self._lang.addItems(["tr", "en"])
        self._theme = QComboBox(self)
        self._theme.addItems(list(THEMES))
        self._mode = QComboBox(self)
        self._mode.addItems(["gui", "avatar"])

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
        self._pack_path = QLineEdit(self)
        self._pack_name = QLineEdit(self)
        self._pack_pick = QPushButton(self)
        self._pack_build = QPushButton(self)

        form = QFormLayout()
        form.addRow("Dil", self._lang)
        form.addRow("Tema", self._theme)
        form.addRow("Mod", self._mode)
        form.addRow("Sağlayıcı", self._provider_type)
        form.addRow("URL", self._provider_url)
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
        form.addRow("Fotoğraf", self._pack_path)
        form.addRow("Paket adı", self._pack_name)
        form.addRow("", self._pack_pick)
        form.addRow("", self._pack_build)

        self._status = QLabel("", self)
        self._status.setObjectName("muted")
        save_btn = QPushButton(self)
        save_btn.clicked.connect(self.save)
        close_btn = QPushButton(self)
        close_btn.clicked.connect(self.close)
        buttons = QHBoxLayout()
        buttons.addWidget(save_btn)
        buttons.addWidget(close_btn)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._status)
        layout.addLayout(buttons)

        self._save_btn = save_btn
        self._close_btn = close_btn
        self._form_labels = []  # filled lazily via retranslate store

        self._pack_pick.clicked.connect(self._pick_photo)
        self._pack_build.clicked.connect(self._build_pack)

        self.load()
        self.retranslate()

    def retranslate(self) -> None:
        t = i18n.t
        self.setWindowTitle(t("settings.title"))
        self._save_btn.setText(t("settings.save"))
        self._close_btn.setText(t("settings.close"))
        self._pack_pick.setText(t("settings.pack_pick"))
        self._pack_build.setText(t("settings.pack_build"))
        self._pack_name.setPlaceholderText(t("settings.pack_name"))
        # combo item texts (order matches indices)
        self._lang.setItemText(0, t("settings.lang_tr"))
        self._lang.setItemText(1, t("settings.lang_en"))
        self._theme.setItemText(0, t("settings.theme_dark"))
        self._theme.setItemText(1, t("settings.theme_light"))
        self._mode.setItemText(0, t("settings.mode") + ": GUI")
        self._mode.setItemText(1, t("settings.mode") + ": Avatar")

    def load(self) -> None:
        settings = self._read(self._settings_path)
        secrets = self._read(self._secrets_path)
        prefs = load_prefs(self._ui_json_path)
        self._lang.setCurrentIndex(0 if prefs.lang == "tr" else 1)
        self._theme.setCurrentIndex(list(THEMES).index(prefs.theme))
        self._mode.setCurrentIndex(0 if (prefs.mode or "gui") == "gui" else 1)
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
        lang = "tr" if self._lang.currentIndex() == 0 else "en"
        theme = self._theme.currentText()
        mode = "gui" if self._mode.currentIndex() == 0 else "avatar"
        old = load_prefs(self._ui_json_path)
        save_prefs(self._ui_json_path, UiPrefs(mode=mode, theme=theme, lang=lang))
        if lang != i18n.current:
            i18n.set_language(lang)
            self.language_changed.emit(lang)
            self.retranslate()
        if theme != old.theme:
            self.theme_changed.emit(theme)
        self._status.setText(i18n.t("settings.save_restart_note"))

    def _pick_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Fotoğraf", str(Path.home()), "Images (*.png *.jpg *.jpeg)"
        )
        if path:
            self._pack_path.setText(path)
            if not self._pack_name.text().strip():
                self._pack_name.setText(Path(path).stem)

    def _build_pack(self) -> None:
        src = self._pack_path.text().strip()
        if not src:
            self._status.setText(i18n.t("settings.pack_bad_image"))
            return
        try:
            name = sanitize_pack_name(self._pack_name.text() or Path(src).stem)
        except PackError:
            self._status.setText(i18n.t("settings.pack_bad_image"))
            return
        avatars_root = Path(__file__).resolve().parent.parent / "assets" / "avatars"
        out = avatars_root / name
        try:
            self.setCursor(Qt.CursorShape.WaitCursor)
            build_pack(Path(src), out, name)
        except PackError as exc:
            msg = (
                i18n.t("settings.pack_exists", name=name)
                if "exists" in str(exc)
                else i18n.t("settings.pack_bad_image")
            )
            self._status.setText(msg)
        except Exception:
            self._status.setText(i18n.t("settings.pack_bad_image"))
        else:
            self._status.setText(i18n.t("settings.pack_success", name=name))
            self._avatar.clear()
            self._avatar.addItems(self._list_avatars())
            idx = self._avatar.findText(name)
            if idx >= 0:
                self._avatar.setCurrentIndex(idx)
        finally:
            self.unsetCursor()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.hide()
        event.ignore()

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

"""Settings window v2: general (lang/theme/mode), provider, screen, perms, packs."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.avatar.pack import PackError, build_pack, sanitize_pack_name
from ui.i18n import i18n, language_bridge
from ui.paths import SECRETS_PATH, SETTINGS_PATH, ui_json_path
from ui.prefs import THEMES, load_prefs, save_prefs, UiPrefs

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
        settings_path: Path | None = None,
        secrets_path: Path | None = None,
        ui_json: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settings_win")
        self.setMinimumWidth(460)
        self._settings_path = settings_path or SETTINGS_PATH
        self._secrets_path = secrets_path or SECRETS_PATH
        self._ui_json = ui_json or ui_json_path()
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

        # --- general section ---
        self._lang = QComboBox(self)
        self._lang.addItems(["tr", "en"])
        self._theme = QComboBox(self)
        self._theme.addItems(list(THEMES))
        self._mode = QComboBox(self)
        self._mode.addItems(["gui", "avatar"])
        general_form = QFormLayout()
        self._lbl_lang = QLabel(self)
        self._lbl_theme = QLabel(self)
        self._lbl_mode = QLabel(self)
        general_form.addRow(self._lbl_lang, self._lang)
        general_form.addRow(self._lbl_theme, self._theme)
        general_form.addRow(self._lbl_mode, self._mode)
        general_box = QGroupBox(self)
        general_box.setLayout(general_form)

        # --- provider section ---
        self._provider_type = QComboBox(self)
        self._provider_type.addItems(PROVIDER_TYPES)
        self._provider_url = QLineEdit(self)
        self._provider_model = QLineEdit(self)
        self._provider_key = QLineEdit(self)
        self._provider_key.setEchoMode(QLineEdit.EchoMode.Password)
        provider_form = QFormLayout()
        self._lbl_provider_type = QLabel(self)
        self._lbl_provider_url = QLabel(self)
        self._lbl_provider_model = QLabel(self)
        self._lbl_provider_key = QLabel(self)
        provider_form.addRow(self._lbl_provider_type, self._provider_type)
        provider_form.addRow(self._lbl_provider_url, self._provider_url)
        provider_form.addRow(self._lbl_provider_model, self._provider_model)
        provider_form.addRow(self._lbl_provider_key, self._provider_key)
        provider_box = QGroupBox(self)
        provider_box.setLayout(provider_form)

        # --- screen control section ---
        self._sc_host = QLineEdit(self)
        self._sc_port = QSpinBox(self)
        self._sc_port.setRange(1, 65535)
        self._sc_key = QLineEdit(self)
        self._sc_key.setEchoMode(QLineEdit.EchoMode.Password)
        sc_form = QFormLayout()
        self._lbl_sc_host = QLabel(self)
        self._lbl_sc_port = QLabel(self)
        self._lbl_sc_key = QLabel(self)
        sc_form.addRow(self._lbl_sc_host, self._sc_host)
        sc_form.addRow(self._lbl_sc_port, self._sc_port)
        sc_form.addRow(self._lbl_sc_key, self._sc_key)
        sc_box = QGroupBox(self)
        sc_box.setLayout(sc_form)

        # --- permissions section ---
        self._perm_default = QComboBox(self)
        self._perm_default.addItems(PERMISSION_LEVELS)
        self._perm_tools = {}
        perm_form = QFormLayout()
        self._lbl_perm_default = QLabel(self)
        perm_form.addRow(self._lbl_perm_default, self._perm_default)
        for tool in KNOWN_TOOLS:
            combo = QComboBox(self)
            combo.addItems(PERMISSION_LEVELS)
            self._perm_tools[tool] = combo
            lbl = QLabel(tool, self)
            perm_form.addRow(lbl, combo)
        perm_box = QGroupBox(self)
        perm_box.setLayout(perm_form)

        # --- avatar section ---
        self._avatar = QComboBox(self)
        self._pack_path = QLineEdit(self)
        self._pack_name = QLineEdit(self)
        self._pack_pick = QPushButton(self)
        self._pack_build = QPushButton(self)
        avatar_form = QFormLayout()
        self._lbl_avatar = QLabel(self)
        self._lbl_pack_photo = QLabel(self)
        self._lbl_pack_name = QLabel(self)
        avatar_form.addRow(self._lbl_avatar, self._avatar)
        avatar_form.addRow(self._lbl_pack_photo, self._pack_path)
        avatar_form.addRow(self._lbl_pack_name, self._pack_name)
        avatar_form.addRow("", self._pack_pick)
        avatar_form.addRow("", self._pack_build)
        avatar_box = QGroupBox(self)
        avatar_box.setLayout(avatar_form)

        self._status = QLabel("", self)
        self._status.setObjectName("muted")
        self._save_btn = QPushButton(self)
        self._save_btn.clicked.connect(self.save)
        self._close_btn = QPushButton(self)
        self._close_btn.clicked.connect(self.close)
        buttons = QHBoxLayout()
        buttons.addWidget(self._save_btn)
        buttons.addWidget(self._close_btn)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(general_box)
        layout.addWidget(provider_box)
        layout.addWidget(sc_box)
        layout.addWidget(perm_box)
        layout.addWidget(avatar_box)
        layout.addWidget(self._status)
        layout.addLayout(buttons)

        self._pack_pick.clicked.connect(self._pick_photo)
        self._pack_build.clicked.connect(self._build_pack)
        self._pack_build.setEnabled(False)
        self._pack_path.textChanged.connect(self._update_build_enabled)
        self._pack_name.textChanged.connect(self._update_build_enabled)

        language_bridge.changed.connect(self._on_language_changed)

        self.load()
        self.retranslate()

    def _on_language_changed(self, lang: str) -> None:
        self.retranslate()
        self.language_changed.emit(lang)

    def retranslate(self) -> None:
        t = i18n.t
        self.setWindowTitle(t("settings.title"))
        self._save_btn.setText(t("settings.save"))
        self._close_btn.setText(t("settings.close"))
        self._pack_pick.setText(t("settings.pack_pick"))
        self._pack_build.setText(t("settings.pack_build"))
        self._pack_name.setPlaceholderText(t("settings.pack_name"))
        self._lbl_lang.setText(t("settings.lang"))
        self._lbl_theme.setText(t("settings.theme"))
        self._lbl_mode.setText(t("settings.mode"))
        self._lbl_provider_type.setText(t("settings.provider_type"))
        self._lbl_provider_url.setText(t("settings.provider_url"))
        self._lbl_provider_model.setText(t("settings.provider_model"))
        self._lbl_provider_key.setText(t("settings.provider_key"))
        self._lbl_sc_host.setText(t("settings.sc_host"))
        self._lbl_sc_port.setText(t("settings.sc_port"))
        self._lbl_sc_key.setText(t("settings.sc_key"))
        self._lbl_perm_default.setText(t("settings.perm_default"))
        self._lbl_avatar.setText(t("settings.section_avatar"))
        self._lbl_pack_photo.setText(t("settings.pack_pick"))
        self._lbl_pack_name.setText(t("settings.pack_name"))
        self._lang.setItemText(0, t("settings.lang_tr"))
        self._lang.setItemText(1, t("settings.lang_en"))
        self._theme.setItemText(0, t("settings.theme_dark"))
        self._theme.setItemText(1, t("settings.theme_light"))
        self._mode.setItemText(0, "GUI")
        self._mode.setItemText(1, t("mode.avatar"))

    def load(self) -> None:
        settings = self._read(self._settings_path)
        secrets = self._read(self._secrets_path)
        prefs = load_prefs(self._ui_json)
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
        # Never overwrite an unreadable secrets file with an empty dict (would wipe keys).
        if self._secrets_path.exists():
            try:
                json.loads(self._secrets_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._status.setText(i18n.t("settings.pack_bad_image"))
                return
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
        old = load_prefs(self._ui_json)
        save_prefs(self._ui_json, UiPrefs(mode=mode, theme=theme, lang=lang))
        if lang != i18n.current:
            i18n.set_language(lang)
            self.language_changed.emit(lang)
            self.retranslate()
        if theme != old.theme:
            self.theme_changed.emit(theme)
        self._status.setText(i18n.t("settings.save_restart_note"))

    def _update_build_enabled(self, *_a) -> None:
        ok = bool(self._pack_path.text().strip()) and bool(self._pack_name.text().strip())
        self._pack_build.setEnabled(ok)

    def _pick_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, i18n.t("settings.pack_pick"), str(Path.home()), "Images (*.png *.jpg *.jpeg)"
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
        from core.paths import assets_dir

        avatars_root = assets_dir() / "avatars"
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
        from core.paths import assets_dir

        root = assets_dir() / "avatars"
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
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(payload)
            os.replace(tmp, path)
            if mode is not None:
                os.chmod(path, mode)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

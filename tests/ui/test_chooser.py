import json
from pathlib import Path

import pytest


def test_chooser_constructs_and_returns(tmp_path):
    from PySide6.QtWidgets import QApplication

    from ui.chooser import ModeChooser

    app = QApplication.instance() or QApplication([])
    d = ModeChooser()
    assert d.windowTitle()
    d.reject()
    assert d.result() == 0


def test_restart_into_writes_file(monkeypatch, tmp_path):
    import os
    import sys

    from ui.prefs import load_prefs, restart_into

    ui_json = tmp_path / "ui.json"
    called = {}
    monkeypatch.setattr(os, "execv", lambda *a, **k: called.update(args=a))
    restart_into(ui_json, "gui")
    assert load_prefs(ui_json).mode == "gui"
    assert "args" in called

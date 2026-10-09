import json
import os
from pathlib import Path

from core.agent.runtime import AgentRuntime
from core.bootstrap import build_runtime
from tests.fakes import FakeProvider


def test_build_runtime_wires_everything(tmp_path):
    settings = {
        "provider": {"type": "ollama", "url": "http://127.0.0.1:11434", "model": "m"},
        "screen_control": {"enabled": True, "host": "127.0.0.1", "port": 8745},
        "permissions": {"*": "allow"},
        "agent": {"max_tool_calls": 10, "tool_timeout_s": 30, "model_timeout_s": 60},
    }
    sp = tmp_path / "settings.json"
    sp.write_text(json.dumps(settings))
    kp = tmp_path / "secrets.json"
    kp.write_text(json.dumps({}))
    os.chmod(kp, 0o600)

    rt, events, session = build_runtime(
        settings_path=sp,
        secrets_path=kp,
        provider=FakeProvider([]),
        client_factory=lambda: object(),
    )
    assert isinstance(rt, AgentRuntime)
    names = set(rt.registry.names())
    assert {"screenshot", "ocr_screen", "mouse", "keyboard", "list_windows", "focus_window"} <= names


def test_build_runtime_respects_screen_control_disabled(tmp_path):
    settings = {
        "provider": {"type": "ollama", "url": "http://x", "model": "m"},
        "screen_control": {"enabled": False},
        "permissions": {"*": "deny"},
    }
    sp = tmp_path / "settings.json"
    sp.write_text(json.dumps(settings))
    kp = tmp_path / "secrets.json"
    kp.write_text(json.dumps({}))
    os.chmod(kp, 0o600)
    rt, _, _ = build_runtime(
        settings_path=sp, secrets_path=kp, provider=FakeProvider([]), client_factory=lambda: object()
    )
    assert rt.registry.names() == []

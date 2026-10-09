"""Wire config + providers + tools + runtime into an AgentRuntime."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from core.agent.config import AgentConfig
from core.agent.runtime import AgentRuntime
from core.config import ensure_secrets_mode, load_secrets, load_settings
from core.events import EventBus
from core.paths import config_dir
from core.providers import create_provider
from core.providers.base import ModelProvider
from core.session.store import SessionStore
from core.tools.registry import PermissionPolicy, ToolRegistry
from core.tools.screen_control import register_screen_control

DEFAULT_SETTINGS = config_dir() / "settings.json"
DEFAULT_SECRETS = config_dir() / "secrets.json"


def default_client_factory(settings: dict, secrets: dict) -> Callable[[], Any]:
    def factory():
        import sys

        sdk_path = "/home/xeakaes/screen-control/sdk"
        if sdk_path not in sys.path:
            sys.path.insert(0, sdk_path)
        from screen_control import ScreenControl  # lazy — only when a tool runs

        sc_cfg = settings.get("screen_control") or {}
        return ScreenControl(
            host=sc_cfg.get("host", "127.0.0.1"),
            port=int(sc_cfg.get("port", 8745)),
            api_key=secrets.get("screen_control_api_key"),
        )

    return factory


def build_runtime(
    settings_path: Path | None = None,
    secrets_path: Path | None = None,
    provider: ModelProvider | None = None,
    client_factory: Callable[[], Any] | None = None,
) -> tuple[AgentRuntime, EventBus, SessionStore]:
    settings = load_settings(settings_path or DEFAULT_SETTINGS)
    secrets_path = secrets_path or DEFAULT_SECRETS
    if secrets_path.exists():
        ensure_secrets_mode(secrets_path)
        secrets = load_secrets(secrets_path)
    else:
        secrets = {}
    if provider is None:
        provider = create_provider(settings, secrets)
    registry = ToolRegistry()
    sc_cfg = settings.get("screen_control") or {}
    if sc_cfg.get("enabled", False):
        factory = client_factory or default_client_factory(settings, secrets)
        register_screen_control(registry, factory)
    policy = PermissionPolicy(settings.get("permissions") or {"*": "ask"})
    agent_cfg_raw = settings.get("agent") or {}
    agent_config = AgentConfig(
        max_tool_calls=int(agent_cfg_raw.get("max_tool_calls", 10)),
        tool_timeout_s=float(agent_cfg_raw.get("tool_timeout_s", 30)),
        model_timeout_s=float(agent_cfg_raw.get("model_timeout_s", 60)),
    )
    events = EventBus()
    session = SessionStore()
    runtime = AgentRuntime(provider, registry, policy, events, session, agent_config)
    return runtime, events, session

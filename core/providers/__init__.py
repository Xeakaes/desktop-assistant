"""Model provider factory and package exports."""

from __future__ import annotations

from core.providers.base import ModelProvider, ProviderError
from core.providers.ollama import OllamaProvider
from core.providers.openai_compat import OpenAICompatProvider


def _url(provider_cfg: dict, default: str, secrets: dict | None = None) -> str:
    value = provider_cfg.get("url") or default
    return value.rstrip("/")


def _vision(provider_cfg: dict) -> bool:
    """Model-level vision switch (provider.vision); defaults to enabled."""
    return bool(provider_cfg.get("vision", True))


def create_provider(
    settings: dict, secrets: dict, session=None
) -> ModelProvider:
    provider_cfg = settings.get("provider") or {}
    ptype = provider_cfg.get("type", "ollama")
    timeout_s = float((settings.get("agent") or {}).get("model_timeout_s", 60))
    vision = _vision(provider_cfg)
    if ptype == "ollama":
        return OllamaProvider(
            base_url=_url(provider_cfg, "http://127.0.0.1:11434"),
            model=provider_cfg.get("model", "llama3.2"),
            api_key=secrets.get("ollama_api_key"),
            timeout_s=timeout_s,
            session=session,
            supports_vision=vision,
        )
    if ptype == "openai_compat":
        api_key = secrets.get("api_key") or secrets.get("openai_api_key")
        if not api_key:
            raise ProviderError(
                "openai_compat provider requires secrets.api_key",
                error_code="missing_api_key",
            )
        return OpenAICompatProvider(
            base_url=_url(provider_cfg, "https://api.openai.com/v1"),
            api_key=api_key,
            model=provider_cfg.get("model"),
            timeout_s=timeout_s,
            session=session,
            supports_vision=vision,
        )
    if ptype == "nvidia":
        api_key = secrets.get("nvidia_api_key")
        if not api_key:
            raise ProviderError(
                "nvidia provider requires secrets.nvidia_api_key",
                error_code="missing_api_key",
            )
        return OpenAICompatProvider(
            base_url=_url(provider_cfg, "https://integrate.api.nvidia.com/v1"),
            api_key=api_key,
            model=provider_cfg.get("model"),
            timeout_s=timeout_s,
            session=session,
            supports_vision=vision,
        )
    if ptype == "groq":
        api_key = secrets.get("groq_api_key")
        if not api_key:
            raise ProviderError(
                "groq provider requires secrets.groq_api_key",
                error_code="missing_api_key",
            )
        return OpenAICompatProvider(
            base_url=_url(provider_cfg, "https://api.groq.com/openai/v1"),
            api_key=api_key,
            model=provider_cfg.get("model"),
            timeout_s=timeout_s,
            session=session,
            supports_vision=vision,
        )
    if ptype == "google":
        api_key = secrets.get("google_api_key")
        if not api_key:
            raise ProviderError(
                "google provider requires secrets.google_api_key",
                error_code="missing_api_key",
            )
        return OpenAICompatProvider(
            base_url=_url(
                provider_cfg, "https://generativelanguage.googleapis.com/v1beta/openai"
            ),
            api_key=api_key,
            model=provider_cfg.get("model"),
            timeout_s=timeout_s,
            session=session,
            supports_vision=vision,
        )
    if ptype == "nararouter":
        api_key = secrets.get("nararouter_api_key")
        if not api_key:
            raise ProviderError(
                "nararouter provider requires secrets.nararouter_api_key",
                error_code="missing_api_key",
            )
        url = _url(provider_cfg, "") or secrets.get(
            "openai_compatible_url_for_nararouter", ""
        )
        url = url.rstrip("/")
        if url.endswith("/chat/completions"):
            url = url[: -len("/chat/completions")]
        return OpenAICompatProvider(
            base_url=url,
            api_key=api_key,
            model=provider_cfg.get("model"),
            timeout_s=timeout_s,
            session=session,
            supports_vision=vision,
        )
    raise ProviderError(f"unknown provider type: {ptype}", error_code="unknown_provider")

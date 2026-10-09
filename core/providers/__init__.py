"""Model provider factory and package exports."""

from __future__ import annotations

from core.providers.base import ModelProvider, ProviderError
from core.providers.ollama import OllamaProvider
from core.providers.openai_compat import OpenAICompatProvider


def create_provider(
    settings: dict, secrets: dict, session=None
) -> ModelProvider:
    provider_cfg = settings.get("provider") or {}
    ptype = provider_cfg.get("type", "ollama")
    timeout_s = float((settings.get("agent") or {}).get("model_timeout_s", 60))
    if ptype == "ollama":
        return OllamaProvider(
            base_url=provider_cfg.get("url", "http://127.0.0.1:11434"),
            model=provider_cfg.get("model", "llama3.2"),
            api_key=secrets.get("ollama_api_key"),
            timeout_s=timeout_s,
            session=session,
        )
    if ptype == "openai_compat":
        api_key = secrets.get("api_key") or secrets.get("openai_api_key")
        if not api_key:
            raise ProviderError(
                "openai_compat provider requires secrets.api_key",
                error_code="missing_api_key",
            )
        return OpenAICompatProvider(
            base_url=provider_cfg.get("url", "https://api.openai.com/v1"),
            api_key=api_key,
            model=provider_cfg.get("model"),
            timeout_s=timeout_s,
            session=session,
        )
    if ptype == "nvidia":
        api_key = secrets.get("nvidia_api_key")
        if not api_key:
            raise ProviderError(
                "nvidia provider requires secrets.nvidia_api_key",
                error_code="missing_api_key",
            )
        return OpenAICompatProvider(
            base_url=provider_cfg.get("url", "https://integrate.api.nvidia.com/v1"),
            api_key=api_key,
            model=provider_cfg.get("model"),
            timeout_s=timeout_s,
            session=session,
        )
    if ptype == "nararouter":
        api_key = secrets.get("nararouter_api_key")
        if not api_key:
            raise ProviderError(
                "nararouter provider requires secrets.nararouter_api_key",
                error_code="missing_api_key",
            )
        url = provider_cfg.get("url") or secrets.get(
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
        )
    raise ProviderError(f"unknown provider type: {ptype}", error_code="unknown_provider")

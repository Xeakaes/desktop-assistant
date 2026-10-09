import pytest
from core.providers import create_provider
from core.providers.base import ProviderError
from core.providers.ollama import OllamaProvider
from core.providers.openai_compat import OpenAICompatProvider


def test_create_ollama_provider():
    p = create_provider(
        {"provider": {"type": "ollama", "url": "http://127.0.0.1:11434", "model": "m"}},
        {},
    )
    assert isinstance(p, OllamaProvider) and p.model == "m"


def test_create_openai_compat_requires_api_key():
    with pytest.raises(ProviderError) as ei:
        create_provider({"provider": {"type": "openai_compat", "model": "m"}}, {})
    assert ei.value.error_code == "missing_api_key"


def test_create_openai_compat_uses_api_key_secret():
    p = create_provider(
        {"provider": {"type": "openai_compat", "url": "http://x/v1", "model": "m"}},
        {"api_key": "sk-test"},
    )
    assert isinstance(p, OpenAICompatProvider) and p.api_key == "sk-test"


def test_create_nvidia_profile():
    p = create_provider(
        {"provider": {"type": "nvidia", "model": "meta/llama-3.1-8b-instruct"}},
        {"nvidia_api_key": "nvapi-x"},
    )
    assert isinstance(p, OpenAICompatProvider)
    assert p.api_key == "nvapi-x"
    assert "integrate.api.nvidia.com" in p.base_url


def test_create_nararouter_profile_strips_chat_completions():
    p = create_provider(
        {"provider": {"type": "nararouter", "model": "m"}},
        {
            "nararouter_api_key": "sk-nry-x",
            "openai_compatible_url_for_nararouter": "https://router.example/v1/chat/completions",
        },
    )
    assert isinstance(p, OpenAICompatProvider)
    assert p.base_url == "https://router.example/v1"
    assert p.api_key == "sk-nry-x"


def test_create_unknown_type():
    with pytest.raises(ProviderError) as ei:
        create_provider({"provider": {"type": "nope"}}, {})
    assert ei.value.error_code == "unknown_provider"


def test_create_groq_profile():
    p = create_provider(
        {"provider": {"type": "groq", "model": "qwen/qwen3.8-27b"}},
        {"groq_api_key": "gsk_x"},
    )
    assert isinstance(p, OpenAICompatProvider)
    assert p.api_key == "gsk_x"
    assert "api.groq.com" in p.base_url
    assert p.base_url.endswith("/openai/v1")


def test_create_groq_missing_key():
    with pytest.raises(ProviderError) as ei:
        create_provider({"provider": {"type": "groq"}}, {})
    assert ei.value.error_code == "missing_api_key"


def test_create_google_profile():
    p = create_provider(
        {"provider": {"type": "google", "model": "gemini-3.8-flash"}},
        {"google_api_key": "AIza-x"},
    )
    assert isinstance(p, OpenAICompatProvider)
    assert p.api_key == "AIza-x"
    assert "generativelanguage.googleapis.com" in p.base_url
    assert p.base_url.endswith("/v1beta/openai")


def test_create_google_missing_key():
    with pytest.raises(ProviderError) as ei:
        create_provider({"provider": {"type": "google"}}, {})
    assert ei.value.error_code == "missing_api_key"


def test_create_groq_empty_url_uses_default():
    p = create_provider(
        {"provider": {"type": "groq", "url": "", "model": "m"}},
        {"groq_api_key": "gsk_x"},
    )
    assert p.base_url == "https://api.groq.com/openai/v1"


def test_create_openai_compat_empty_url_uses_openai_default():
    p = create_provider(
        {"provider": {"type": "openai_compat", "url": "", "model": "m"}},
        {"api_key": "sk-x"},
    )
    assert p.base_url == "https://api.openai.com/v1"


def test_create_ollama_empty_url_uses_default():
    p = create_provider(
        {"provider": {"type": "ollama", "url": "", "model": "m"}},
        {},
    )
    assert p.base_url == "http://127.0.0.1:11434"


def test_create_nvidia_empty_url_uses_default():
    p = create_provider(
        {"provider": {"type": "nvidia", "url": "", "model": "m"}},
        {"nvidia_api_key": "nvapi-x"},
    )
    assert p.base_url == "https://integrate.api.nvidia.com/v1"


def test_create_google_empty_url_uses_default():
    p = create_provider(
        {"provider": {"type": "google", "url": "", "model": "m"}},
        {"google_api_key": "AIza-x"},
    )
    assert "generativelanguage.googleapis.com" in p.base_url

"""Unit tests for the LLM engine and provider registry (no API calls)."""

from app.infrastructure.llm.providers import (
    PROVIDERS,
    check_provider_credentials,
    get_available_providers,
    resolve_model_string,
    provider_key_from_model,
)


def test_providers_registry_has_expected_keys() -> None:
    assert "openai" in PROVIDERS
    assert "anthropic" in PROVIDERS
    assert "google_genai" in PROVIDERS
    assert "vertex_ai" in PROVIDERS


def test_resolve_model_string_adds_prefix() -> None:
    assert resolve_model_string("gpt-4o-mini") == "openai/gpt-4o-mini"
    assert resolve_model_string("claude-3-5-sonnet-20241022") == "anthropic/claude-3-5-sonnet-20241022"
    assert resolve_model_string("gemini-2.5-flash") == "gemini/gemini-2.5-flash"


def test_resolve_model_string_keeps_existing_prefix() -> None:
    assert resolve_model_string("openai/gpt-4o") == "openai/gpt-4o"
    assert resolve_model_string("vertex_ai/gemini-pro") == "vertex_ai/gemini-pro"


def test_provider_key_from_model() -> None:
    assert provider_key_from_model("openai/gpt-4o") == "openai"
    assert provider_key_from_model("anthropic/claude-3-haiku") == "anthropic"
    assert provider_key_from_model("gemini/gemini-pro") == "google_genai"
    assert provider_key_from_model("vertex_ai/gemini-pro") == "vertex_ai"


def test_check_credentials_missing() -> None:
    ok, msg = check_provider_credentials("openai")
    assert isinstance(ok, bool)
    assert isinstance(msg, str)


def test_check_credentials_unknown_provider() -> None:
    ok, msg = check_provider_credentials("unknown_provider")
    assert ok is False
    assert "Unknown provider" in msg


def test_get_available_providers_returns_list() -> None:
    providers = get_available_providers()
    assert isinstance(providers, list)
    assert len(providers) == len(PROVIDERS)
    for p in providers:
        assert "key" in p
        assert "available" in p

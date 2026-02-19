"""Provider registry and credential validation.

Each supported LLM provider is registered here with the environment
variables it requires.  The engine checks credentials before making
API calls and returns a human-readable error when keys are missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.registry.settings import settings


@dataclass(frozen=True)
class ProviderSpec:
    """Describes a supported LLM provider and its credential requirements."""

    name: str
    litellm_prefix: str
    required_env: list[str] = field(default_factory=list)
    optional_env: list[str] = field(default_factory=list)
    description: str = ""


# ---------------------------------------------------------------------------
# Provider definitions
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        name="OpenAI",
        litellm_prefix="openai/",
        required_env=["OPENAI_API_KEY"],
        description="OpenAI GPT models (gpt-4o, gpt-4o-mini, etc.)",
    ),
    "anthropic": ProviderSpec(
        name="Anthropic",
        litellm_prefix="anthropic/",
        required_env=["ANTHROPIC_API_KEY"],
        description="Anthropic Claude models (claude-3.5-sonnet, etc.)",
    ),
    "google_genai": ProviderSpec(
        name="Google GenAI",
        litellm_prefix="gemini/",
        required_env=["GEMINI_API_KEY"],
        description="Google Gemini via AI Studio API key",
    ),
    "vertex_ai": ProviderSpec(
        name="Vertex AI",
        litellm_prefix="vertex_ai/",
        required_env=["GOOGLE_CLOUD_PROJECT"],
        optional_env=["VERTEX_AI_LOCATION"],
        description="Google Vertex AI (Gemini, Claude, etc.)",
    ),
}


def _resolve_credential(env_var: str) -> str:
    """Read a credential value from settings (env-backed)."""
    return getattr(settings, env_var, "") or ""


def check_provider_credentials(provider_key: str) -> tuple[bool, str]:
    """Validate that the required credentials for a provider are set.

    Returns:
        A tuple of (is_available, message).
    """
    if provider_key not in PROVIDERS:
        return False, f"Unknown provider '{provider_key}'. Available: {list(PROVIDERS.keys())}"

    spec = PROVIDERS[provider_key]
    missing = [var for var in spec.required_env if not _resolve_credential(var)]

    if missing:
        return False, (
            f"Provider '{spec.name}' is not configured. Missing environment variable(s): {', '.join(missing)}"
        )

    return True, f"Provider '{spec.name}' is available."


def get_available_providers() -> list[dict[str, Any]]:
    """Return metadata about all providers and their availability."""
    result = []
    for key, spec in PROVIDERS.items():
        available, message = check_provider_credentials(key)
        result.append(
            {
                "key": key,
                "name": spec.name,
                "description": spec.description,
                "available": available,
                "message": message,
            }
        )
    return result


def resolve_model_string(model: str) -> str:
    """Ensure a model string includes the LiteLLM provider prefix.

    If the user passes ``"gpt-4o-mini"`` it becomes ``"openai/gpt-4o-mini"``.
    If they pass ``"openai/gpt-4o-mini"`` it stays as-is.
    """
    for spec in PROVIDERS.values():
        if model.startswith(spec.litellm_prefix):
            return model

    # Auto-detect provider from well-known model name prefixes.
    prefix_hints: dict[str, str] = {
        "gpt-": "openai/",
        "o1-": "openai/",
        "o3-": "openai/",
        "claude-": "anthropic/",
        "gemini-": "gemini/",
    }
    for hint, prefix in prefix_hints.items():
        if model.startswith(hint):
            return f"{prefix}{model}"

    # Default: pass through (LiteLLM will try its own detection).
    return model


def provider_key_from_model(model: str) -> str | None:
    """Extract the provider key from a model string like ``openai/gpt-4o``."""
    resolved = resolve_model_string(model)
    for key, spec in PROVIDERS.items():
        if resolved.startswith(spec.litellm_prefix):
            return key
    return None

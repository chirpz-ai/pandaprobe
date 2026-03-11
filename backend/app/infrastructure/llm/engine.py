"""Universal LLM engine powered by LiteLLM.

A single ``LLMEngine`` class handles all LLM calls across every
supported provider.  Callers simply pass a model string (e.g.
``"openai/gpt-4o-mini"`` or ``"anthropic/claude-3-5-sonnet-20241022"``)
and the engine routes the request via LiteLLM, validates credentials,
and parses the structured response.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from typing import TypeVar

import litellm
from pydantic import BaseModel

from app.infrastructure.llm.providers import (
    PROVIDERS,
    check_provider_credentials,
    provider_key_from_model,
    resolve_model_string,
)
from app.logging import logger
from app.registry.exceptions import PandaProbeError
from app.registry.settings import settings

T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 3


class LLMEngineError(PandaProbeError):
    """Raised when an LLM call fails after retries."""

    status_code = 502
    detail = "LLM engine request failed."


class ProviderNotConfiguredError(PandaProbeError):
    """Raised when the requested provider's credentials are missing."""

    status_code = 422
    detail = "LLM provider not configured."


class LLMEngine:
    """Universal LLM gateway for evaluation metrics.

    Uses LiteLLM under the hood so that any supported provider can be
    called with a single interface.  Credentials are read from the
    application settings (environment variables) and injected into
    LiteLLM at call time.
    """

    def __init__(self) -> None:
        """Initialise the engine and push credentials into the environment.

        LiteLLM reads API keys from ``os.environ`` at call time, so we
        sync our pydantic-settings values into the process environment.
        """
        self._sync_credentials()
        self._embedding_cache: dict[str, list[float]] = {}

    def _sync_credentials(self) -> None:
        """Push credential settings into ``os.environ`` for LiteLLM."""
        env_map: dict[str, str] = {
            "OPENAI_API_KEY": settings.OPENAI_API_KEY,
            "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,
            "GEMINI_API_KEY": settings.GEMINI_API_KEY,
            "GOOGLE_CLOUD_PROJECT": settings.GOOGLE_CLOUD_PROJECT,
            "VERTEXAI_LOCATION": settings.VERTEX_AI_LOCATION,
            "VERTEXAI_PROJECT": settings.GOOGLE_CLOUD_PROJECT,
        }
        for key, value in env_map.items():
            if value:
                os.environ[key] = value

    @property
    def default_model(self) -> str:
        """Return the model string configured as the default evaluation LLM."""
        return resolve_model_string(settings.EVAL_LLM_MODEL)

    def available_providers(self) -> list[dict]:
        """Return a list of providers with their availability status."""
        from app.infrastructure.llm.providers import get_available_providers

        return get_available_providers()

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> T:
        """Send a prompt and parse the response into a Pydantic model.

        Args:
            prompt: The user prompt text.
            response_schema: Pydantic model class for the expected response.
            model: LiteLLM model string (e.g. ``"openai/gpt-4o-mini"``).
                   Defaults to ``settings.EVAL_LLM_MODEL``.
            temperature: Sampling temperature. Defaults to
                   ``settings.EVAL_LLM_TEMPERATURE``.

        Returns:
            An instance of *response_schema* parsed from the LLM output.

        Raises:
            ProviderNotConfiguredError: If the provider's credentials are missing.
            LLMEngineError: On API or parsing failure after retries.
        """
        resolved_model = resolve_model_string(model or settings.EVAL_LLM_MODEL)
        temp = temperature if temperature is not None else settings.EVAL_LLM_TEMPERATURE

        # Validate credentials before calling.
        provider_key = provider_key_from_model(resolved_model)
        if provider_key:
            ok, msg = check_provider_credentials(provider_key)
            if not ok:
                raise ProviderNotConfiguredError(msg)

        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return await self._call(resolved_model, prompt, response_schema, temp)
            except (ProviderNotConfiguredError, LLMEngineError):
                raise
            except Exception as exc:
                last_error = exc
                logger.warning("llm_engine_retry", attempt=attempt, model=resolved_model, error=str(exc))

        raise LLMEngineError(f"LLM call to {resolved_model} failed after {MAX_RETRIES} attempts: {last_error}")

    async def _call(
        self,
        model: str,
        prompt: str,
        response_schema: type[T],
        temperature: float,
    ) -> T:
        """Make the actual LiteLLM call and parse the response."""
        messages = [
            {"role": "system", "content": "You are an expert evaluation judge. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ]

        # Build response_format using the reliable JSON schema approach.
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "schema": response_schema.model_json_schema(),
                "name": response_schema.__name__,
                "strict": True,
            },
        }

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
            )
            raw = response.choices[0].message.content or ""
            return self._parse_response(raw, response_schema)
        except Exception:
            # Fallback: try without structured output (some models/providers
            # don't support json_schema mode).
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            raw = response.choices[0].message.content or ""
            return self._parse_response(raw, response_schema)

    async def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        """Batch-embed texts via ``litellm.aembedding()``.

        Results are cached by content hash so repeated calls with the
        same text are free.  The cache lives on the instance -- scoped
        to the lifetime of this ``LLMEngine`` object (typically one
        Celery task execution).
        """
        resolved_model = resolve_model_string(model or settings.EVAL_EMBEDDING_MODEL)

        provider_key = provider_key_from_model(resolved_model)
        if provider_key:
            ok, msg = check_provider_credentials(provider_key)
            if not ok:
                raise ProviderNotConfiguredError(msg)

        hashes = [hashlib.sha256(t.encode()).hexdigest() for t in texts]
        uncached_indices = [i for i, h in enumerate(hashes) if h not in self._embedding_cache]

        if uncached_indices:
            uncached_texts = [texts[i] for i in uncached_indices]
            response = await litellm.aembedding(model=resolved_model, input=uncached_texts)
            for idx, item in zip(uncached_indices, response.data):
                self._embedding_cache[hashes[idx]] = item["embedding"]

        return [self._embedding_cache[h] for h in hashes]

    @staticmethod
    def cosine_distance(vec_a: list[float], vec_b: list[float]) -> float:
        """Return cosine distance (0 = identical, 1 = orthogonal) between two vectors."""
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 1.0
        similarity = dot / (norm_a * norm_b)
        return max(0.0, min(1.0, 1.0 - similarity))

    @staticmethod
    def _parse_response(raw: str, schema: type[T]) -> T:
        """Extract JSON from the raw LLM response and validate it."""
        text = raw.strip()
        # Strip markdown code fences if present.
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return schema.model_validate(json.loads(text))

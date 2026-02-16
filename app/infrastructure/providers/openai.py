"""OpenAI-compatible LLM provider for evaluation judges.

Uses the ``openai`` Python SDK with structured-output parsing
(``response_format``) so that every response conforms to the
requested Pydantic schema.
"""

from __future__ import annotations

import json
from typing import TypeVar

import openai
from pydantic import BaseModel

from app.infrastructure.providers.base import AbstractLLMProvider
from app.logging import logger
from app.registry.exceptions import OpentracerError

T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 3


class LLMProviderError(OpentracerError):
    """Raised when the LLM provider call fails after retries."""

    status_code = 502
    detail = "LLM provider request failed."


class OpenAIProvider(AbstractLLMProvider):
    """Judge provider backed by the OpenAI chat-completions API.

    Also works with any OpenAI-compatible endpoint (Azure, local vLLM,
    etc.) by setting ``base_url``.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ) -> None:
        """Initialise the OpenAI async client.

        Args:
            api_key: OpenAI (or compatible) API key.
            model: Model identifier to use for judge calls.
            base_url: Optional custom base URL for the API.
        """
        self._model = model
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    @property
    def model_name(self) -> str:
        """Return the model identifier."""
        return self._model

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        *,
        temperature: float = 0.0,
    ) -> T:
        """Call OpenAI and parse the structured JSON response.

        Attempts up to ``MAX_RETRIES`` times on transient failures.
        Falls back to manual JSON parsing if the SDK's native
        structured-output feature is unavailable.
        """
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return await self._call_with_structured_output(prompt, response_schema, temperature)
            except (openai.APIConnectionError, openai.RateLimitError, openai.APITimeoutError) as exc:
                last_error = exc
                logger.warning(
                    "openai_transient_error",
                    attempt=attempt,
                    error=str(exc),
                )
            except Exception as exc:
                last_error = exc
                logger.error("openai_call_failed", attempt=attempt, error=str(exc))
                break

        raise LLMProviderError(f"OpenAI call failed after {MAX_RETRIES} attempts: {last_error}")

    async def _call_with_structured_output(
        self,
        prompt: str,
        response_schema: type[T],
        temperature: float,
    ) -> T:
        """Try the beta structured-output API, fall back to manual parsing."""
        try:
            response = await self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You are an expert evaluation judge. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format=response_schema,
                temperature=temperature,
            )
            parsed = response.choices[0].message.parsed
            if parsed is not None:
                return parsed
        except Exception:
            pass

        # Fallback: plain completion + manual JSON parse.
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "You are an expert evaluation judge. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        raw = response.choices[0].message.content or ""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return response_schema.model_validate(json.loads(raw))

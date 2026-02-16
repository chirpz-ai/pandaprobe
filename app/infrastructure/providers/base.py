"""Abstract LLM provider interface for evaluation judges.

Concrete implementations (OpenAI, Anthropic, etc.) live alongside
this file.  The eval worker resolves the active provider from
settings at runtime, so the metric logic never imports a specific SDK.
"""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AbstractLLMProvider(ABC):
    """Contract for any LLM backend used by evaluation metrics."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the identifier of the underlying model (e.g. ``gpt-4o``)."""
        ...

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        *,
        temperature: float = 0.0,
    ) -> T:
        """Send a prompt to the LLM and parse the response into *response_schema*.

        Args:
            prompt: The full prompt text (system + user combined).
            response_schema: A Pydantic model class that the response
                must conform to.
            temperature: Sampling temperature (0 = deterministic).

        Returns:
            An instance of *response_schema* parsed from the LLM output.

        Raises:
            LLMProviderError: On network or parsing failures.
        """
        ...

"""Abstract base class for all evaluation metrics.

Every concrete metric (TaskCompletion, Hallucination, etc.) subclasses
``BaseMetric`` and implements ``evaluate()``.  The eval worker calls
this method with a trace and an LLM provider, keeping the metric logic
completely decoupled from infrastructure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.providers.base import AbstractLLMProvider


class MetricResult(BaseModel):
    """Standard output produced by every metric's ``evaluate()`` call."""

    score: float
    reason: str | None = None
    metadata: dict[str, Any] = {}


class BaseMetric(ABC):
    """Contract that every evaluation metric must fulfill.

    Attributes:
        name: Machine-readable identifier (e.g. ``"task_completion"``).
        threshold: Default pass/fail threshold (0-1 scale).
    """

    name: str
    threshold: float = 0.5

    @abstractmethod
    async def evaluate(
        self,
        trace: Trace,
        provider: AbstractLLMProvider,
        *,
        threshold: float | None = None,
    ) -> MetricResult:
        """Score a trace using this metric.

        Args:
            trace: The full trace entity (with spans).
            provider: An LLM provider to call for judge reasoning.
            threshold: Override the default pass/fail threshold.

        Returns:
            A ``MetricResult`` with score, reason, and optional metadata.
        """
        ...

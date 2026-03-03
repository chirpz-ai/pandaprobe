"""Abstract base class for all evaluation metrics.

Every concrete metric (TaskCompletion, Hallucination, etc.) subclasses
``BaseMetric`` and implements ``evaluate()``.  The eval worker calls
this method with a trace and the LLM engine, keeping the metric logic
completely decoupled from infrastructure details.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.llm.engine import LLMEngine


class MetricResult(BaseModel):
    """Standard output produced by every metric's ``evaluate()`` call."""

    score: float
    reason: str | None = None
    metadata: dict[str, Any] = {}


class BaseMetric(ABC):
    """Contract that every evaluation metric must fulfill.

    Attributes:
        name: Machine-readable identifier (e.g. ``"task_completion"``).
        description: Human-readable explanation of what this metric measures.
        category: Scope of the metric (``"trace"`` or ``"session"``).
        threshold: Default pass/fail threshold (0-1 scale).
    """

    name: str
    description: str = ""
    category: str = "trace"
    threshold: float = 0.5

    @abstractmethod
    async def evaluate(
        self,
        trace: Trace,
        llm: LLMEngine,
        *,
        threshold: float | None = None,
        model: str | None = None,
    ) -> MetricResult:
        """Score a trace using this metric.

        Args:
            trace: The full trace entity (with spans).
            llm: Universal LLM engine for judge reasoning calls.
            threshold: Override the default pass/fail threshold.
            model: Override the default evaluation model string.

        Returns:
            A ``MetricResult`` with score, reason, and optional metadata.
        """
        ...

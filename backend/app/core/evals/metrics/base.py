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

DEFAULT_SIGNAL_WEIGHTS: dict[str, float] = {
    "confidence": 1.0,
    "loop_detection": 1.0,
    "tool_correctness": 0.8,
    "coherence": 1.0,
}


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

    @classmethod
    def get_prompt_preview(cls) -> dict[str, str]:
        """Return actual prompt texts with sample data for preview.

        Subclasses should override this to delegate to their template class.
        """
        return {}

    @abstractmethod
    async def evaluate(
        self,
        trace: Trace,
        llm: LLMEngine,
        *,
        threshold: float | None = None,
        model: str | None = None,
        session_traces: list[Trace] | None = None,
    ) -> MetricResult:
        """Score a trace using this metric.

        Args:
            trace: The full trace entity (with spans).
            llm: Universal LLM engine for judge reasoning calls.
            threshold: Override the default pass/fail threshold.
            model: Override the default evaluation model string.
            session_traces: Previous traces in the same session, ordered
                by ``started_at``.  Only used by metrics that need
                cross-trace context (e.g. ``loop_detection``).

        Returns:
            A ``MetricResult`` with score, reason, and optional metadata.
        """
        ...


class BaseSessionMetric(ABC):
    """Contract for session-level aggregation metrics.

    Session metrics receive precomputed per-trace signals and perform
    pure mathematical aggregation -- they must NOT make LLM or
    embedding calls.

    Attributes:
        name: Machine-readable identifier (e.g. ``"agent_reliability"``).
        description: Human-readable explanation of what this metric measures.
        category: Always ``"session"``.
        threshold: Default pass/fail threshold (0-1 scale).
    """

    name: str
    description: str = ""
    category: str = "session"
    threshold: float = 0.5

    @abstractmethod
    async def evaluate(
        self,
        session_id: str,
        traces: list[Trace],
        llm: LLMEngine,
        *,
        model: str | None = None,
        signal_weights: dict[str, float] | None = None,
        precomputed_signals: dict[str, dict[str, float]] | None = None,
    ) -> MetricResult:
        """Aggregate trace-level signals into a session score.

        Args:
            session_id: The session being evaluated.
            traces: All traces in the session, ordered by ``started_at``.
            llm: LLM engine (available but should not be called).
            model: Model override (passed through but unused).
            signal_weights: Per-signal weight overrides.
            precomputed_signals: Mapping of ``trace_id -> {signal -> score}``.

        Returns:
            A ``MetricResult`` with score, reason, and rich metadata.
        """
        ...

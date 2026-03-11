"""Confidence metric -- LLM-as-judge evaluation of agent decisiveness.

Evaluates whether the agent's actions within a trace were decisive,
appropriate, and well-founded.  Used as a signal for session-level
aggregation (agent_reliability, agent_consistency).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.evals.metrics import register_metric
from app.core.evals.metrics.base import BaseMetric, MetricResult
from app.core.evals.metrics.trace.confidence.schema import ConfidenceVerdict
from app.core.evals.metrics.trace.confidence.template import ConfidenceTemplate

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.llm.engine import LLMEngine


@register_metric("confidence")
class ConfidenceMetric(BaseMetric):
    """Measures agent confidence and decisiveness within a trace."""

    name = "confidence"
    description = "Evaluates whether the agent acted decisively and appropriately."
    category = "trace"
    threshold = 0.5

    @classmethod
    def get_prompt_preview(cls) -> dict[str, str]:
        return ConfidenceTemplate.get_prompt_preview()

    async def evaluate(
        self,
        trace: Trace,
        llm: LLMEngine,
        *,
        threshold: float | None = None,
        model: str | None = None,
        session_traces: list[Trace] | None = None,
    ) -> MetricResult:
        effective_threshold = threshold if threshold is not None else self.threshold

        trace_dict = trace.model_dump(mode="json")
        prompt = ConfidenceTemplate.evaluate_confidence(trace_dict)
        verdict = await llm.generate_structured(
            prompt=prompt,
            response_schema=ConfidenceVerdict,
            model=model,
        )

        return MetricResult(
            score=verdict.confidence,
            reason=verdict.reason,
            metadata={
                "threshold": effective_threshold,
                "success": verdict.confidence >= effective_threshold,
            },
        )

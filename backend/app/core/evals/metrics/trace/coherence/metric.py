"""Coherence metric -- embedding-based input/output alignment.

Measures whether the agent's output logically follows from its input
by computing cosine distance between their embeddings.  No LLM call
is needed -- only embedding API calls.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.evals.metrics import register_metric
from app.core.evals.metrics.base import BaseMetric, MetricResult

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.llm.engine import LLMEngine


def _to_text(value: object) -> str:
    """Serialize a trace input/output value to a plain string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)


@register_metric("coherence")
class CoherenceMetric(BaseMetric):
    """Measures input-output coherence via embedding distance."""

    name = "coherence"
    description = "Evaluates whether the agent's output logically follows from its input."
    category = "trace"
    threshold = 0.5

    async def evaluate(  # noqa: D102
        self,
        trace: Trace,
        llm: LLMEngine,
        *,
        threshold: float | None = None,
        model: str | None = None,
        session_traces: list[Trace] | None = None,
    ) -> MetricResult:
        effective_threshold = threshold if threshold is not None else self.threshold

        input_text = _to_text(trace.input)
        output_text = _to_text(trace.output)

        if not input_text or not output_text:
            return MetricResult(
                score=1.0,
                reason="Input or output is empty; coherence assumed.",
                metadata={"coherence_gap": 0.0, "note": "empty_input_or_output"},
            )

        embeddings = await llm.embed_texts([input_text, output_text])
        gap = llm.cosine_distance(embeddings[0], embeddings[1])
        score = max(0.0, min(1.0, 1.0 - gap))

        return MetricResult(
            score=round(score, 4),
            reason=f"Coherence gap: {gap:.4f}",
            metadata={
                "coherence_gap": round(gap, 4),
                "threshold": effective_threshold,
                "success": score >= effective_threshold,
            },
        )

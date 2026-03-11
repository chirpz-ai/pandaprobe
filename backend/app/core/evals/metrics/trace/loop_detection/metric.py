"""LoopDetection metric -- hybrid semantic + Jaccard repetition detector.

Compares the current trace's output against previous traces in the
session using a combined cosine-similarity x Jaccard-similarity score.
High semantic AND high lexical overlap indicates looping (agent stuck).
High semantic but low lexical overlap indicates valid enumeration.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from app.core.evals.metrics import register_metric
from app.core.evals.metrics.base import BaseMetric, MetricResult

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.llm.engine import LLMEngine

_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would shall should may might can could of in to for on with "
    "at by from as into through during before after above below and "
    "but or nor not so yet both either neither each every all any few "
    "more most other some such no only own same than too very it its".split()
)

DEFAULT_WINDOW = 3


def _to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)


def _tokenize(text: str) -> set[str]:
    """Lowercase tokenization with stop-word removal."""
    tokens = re.findall(r"\w+", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


@register_metric("loop_detection")
class LoopDetectionMetric(BaseMetric):
    """Detects agent looping via hybrid semantic + Jaccard similarity."""

    name = "loop_detection"
    description = "Detects if the agent is stuck repeating itself across traces."
    category = "trace"
    threshold = 0.5

    async def evaluate(
        self,
        trace: Trace,
        llm: LLMEngine,
        *,
        threshold: float | None = None,
        model: str | None = None,
        session_traces: list[Trace] | None = None,
    ) -> MetricResult:
        if not session_traces:
            return MetricResult(
                score=1.0,
                reason="No session context provided; looping cannot be assessed.",
                metadata={"note": "no session context provided"},
            )

        window = session_traces[-DEFAULT_WINDOW:]
        current_text = _to_text(trace.output)
        if not current_text:
            return MetricResult(
                score=1.0,
                reason="Empty output; looping cannot be assessed.",
                metadata={"note": "empty_output"},
            )

        prev_texts = [_to_text(t.output) for t in window]
        prev_texts = [t for t in prev_texts if t]
        if not prev_texts:
            return MetricResult(
                score=1.0,
                reason="No previous outputs to compare.",
                metadata={"note": "no_previous_outputs"},
            )

        all_texts = [current_text] + prev_texts
        embeddings = await llm.embed_texts(all_texts)
        current_embedding = embeddings[0]
        current_tokens = _tokenize(current_text)

        max_hybrid = 0.0
        comparisons = []

        for i, prev_text in enumerate(prev_texts):
            prev_embedding = embeddings[i + 1]
            cos_sim = 1.0 - llm.cosine_distance(current_embedding, prev_embedding)
            jac_sim = _jaccard(current_tokens, _tokenize(prev_text))
            hybrid = cos_sim * jac_sim
            max_hybrid = max(max_hybrid, hybrid)
            comparisons.append({
                "trace_index": len(session_traces) - len(prev_texts) + i,
                "cosine_similarity": round(cos_sim, 4),
                "jaccard_similarity": round(jac_sim, 4),
                "hybrid_score": round(hybrid, 4),
            })

        score = round(max(0.0, min(1.0, 1.0 - max_hybrid)), 4)

        return MetricResult(
            score=score,
            reason=f"Max hybrid repetition score: {max_hybrid:.4f}",
            metadata={
                "window_size": len(prev_texts),
                "max_hybrid": round(max_hybrid, 4),
                "comparisons": comparisons,
                "threshold": threshold or self.threshold,
                "success": score >= (threshold or self.threshold),
            },
        )

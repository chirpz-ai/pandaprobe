"""AgentReliability metric -- TRACER-inspired max-compose + top-k tail risk.

Focuses on worst-case failure risk across a session.  A session with
one catastrophic trace scores poorly even if all others are fine.

This is a pure aggregation function: it receives precomputed per-trace
signals and performs only math -- zero LLM or embedding calls.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from app.core.evals.metrics import register_session_metric
from app.core.evals.metrics.base import DEFAULT_SIGNAL_WEIGHTS, BaseSessionMetric, MetricResult

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.llm.engine import LLMEngine

TOP_K_PERCENTILE = 0.15
ENSEMBLE_WEIGHT_MAX = 0.1


@register_session_metric("agent_reliability")
class AgentReliabilityMetric(BaseSessionMetric):
    """Worst-case failure risk via max-compose + top-k tail risk aggregation."""

    name = "agent_reliability"
    description = (
        "Evaluates worst-case failure risk across a session. "
        "Focuses on the most problematic traces using max-compose + top-k tail risk."
    )
    category = "session"
    threshold = 0.5

    async def evaluate(  # noqa: D102
        self,
        session_id: str,
        traces: list[Trace],
        llm: LLMEngine,
        *,
        model: str | None = None,
        signal_weights: dict[str, float] | None = None,
        precomputed_signals: dict[str, dict[str, float]] | None = None,
    ) -> MetricResult:
        if not precomputed_signals or not traces:
            return MetricResult(
                score=1.0,
                reason="No traces or signals to evaluate.",
                metadata={"note": "empty_session"},
            )

        weights = {**DEFAULT_SIGNAL_WEIGHTS, **(signal_weights or {})}
        w_conf = weights.get("confidence", 1.0)
        w_loop = weights.get("loop_detection", 1.0)
        w_tool = weights.get("tool_correctness", 0.8)
        w_coh = weights.get("coherence", 1.0)

        per_trace_risks: list[float] = []
        per_trace_details: dict[str, dict[str, float]] = {}
        flagged: list[str] = []

        for trace in traces:
            tid = str(trace.trace_id)
            signals = precomputed_signals.get(tid)
            if signals is None or not signals:
                continue

            risk_components: list[float] = []
            detail: dict[str, float] = {}

            if "confidence" in signals:
                conf_risk = 1.0 - signals["confidence"]
                risk_components.append(w_conf * conf_risk)
                detail["confidence_risk"] = round(conf_risk, 4)
            if "loop_detection" in signals:
                loop_risk = 1.0 - signals["loop_detection"]
                risk_components.append(w_loop * loop_risk)
                detail["loop_risk"] = round(loop_risk, 4)
            if "tool_correctness" in signals:
                tool_risk = 1.0 - signals["tool_correctness"]
                risk_components.append(w_tool * tool_risk)
                detail["tool_risk"] = round(tool_risk, 4)
            if "coherence" in signals:
                coh_risk = 1.0 - signals["coherence"]
                risk_components.append(w_coh * coh_risk)
                detail["coherence_risk"] = round(coh_risk, 4)

            if not risk_components:
                continue

            risk = max(risk_components)
            per_trace_risks.append(risk)
            detail["step_risk"] = round(risk, 4)
            per_trace_details[tid] = detail

            if risk > 0.5:
                flagged.append(tid)

        if not per_trace_risks:
            return MetricResult(score=1.0, reason="No evaluable traces.", metadata={})

        sorted_risks = sorted(per_trace_risks, reverse=True)
        k = max(1, math.ceil(len(sorted_risks) * TOP_K_PERCENTILE))
        mean_top_k = sum(sorted_risks[:k]) / k
        max_risk = sorted_risks[0]
        raw_risk = (1 - ENSEMBLE_WEIGHT_MAX) * mean_top_k + ENSEMBLE_WEIGHT_MAX * max_risk
        score = round(max(0.0, min(1.0, 1.0 - raw_risk)), 4)

        n_flagged = len(flagged)
        n_total = len(per_trace_risks)
        if n_flagged == 0:
            reason = f"No elevated risk across {n_total} traces."
        else:
            reason = f"Elevated risk in {n_flagged} of {n_total} traces."

        return MetricResult(
            score=score,
            reason=reason,
            metadata={
                "total_traces_in_session": len(traces),
                "traces_evaluated": n_total,
                "raw_risk": round(raw_risk, 4),
                "signal_weights": weights,
                "per_trace_signals": per_trace_details,
                "flagged_traces": flagged,
                "aggregation": {
                    "method": "max_compose_top_k",
                    "top_k_percentile": TOP_K_PERCENTILE,
                    "ensemble_weight": ENSEMBLE_WEIGHT_MAX,
                    "mean_top_k_risk": round(mean_top_k, 4),
                    "max_risk": round(max_risk, 4),
                },
            },
        )

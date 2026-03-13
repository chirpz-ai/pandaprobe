"""AgentConsistency metric -- SAUP-inspired weighted RMS aggregation.

Measures overall stability across a session.  Unlike reliability
(which focuses on worst moments), consistency penalizes any trace that
deviates from smooth operation.  Many moderate issues score poorly even
if no single trace is catastrophic.

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


@register_session_metric("agent_consistency")
class AgentConsistencyMetric(BaseSessionMetric):
    """Overall session stability via weighted RMS aggregation."""

    name = "agent_consistency"
    description = (
        "Evaluates overall stability across a session. "
        "Penalizes any trace that deviates from smooth operation using weighted RMS."
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

        weighted_uncertainties: list[float] = []
        per_trace_details: dict[str, dict[str, float]] = {}

        for trace in traces:
            tid = str(trace.trace_id)
            signals = precomputed_signals.get(tid)
            if signals is None:
                continue

            conf_risk = 1.0 - signals.get("confidence", 1.0)
            loop_risk = 1.0 - signals.get("loop_detection", 1.0)
            tool_risk = 1.0 - signals.get("tool_correctness", 1.0)
            coh_risk = 1.0 - signals.get("coherence", 1.0)

            penalty = w_loop * loop_risk + w_tool * tool_risk + w_coh * coh_risk
            amplification = 1.0 + penalty
            wu = amplification * (w_conf * conf_risk)

            weighted_uncertainties.append(wu)
            per_trace_details[tid] = {
                "confidence_risk": round(conf_risk, 4),
                "loop_risk": round(loop_risk, 4),
                "tool_risk": round(tool_risk, 4),
                "coherence_risk": round(coh_risk, 4),
                "situational_penalty": round(penalty, 4),
                "weighted_uncertainty": round(wu, 4),
            }

        if not weighted_uncertainties:
            return MetricResult(score=1.0, reason="No evaluable traces.", metadata={})

        rms = math.sqrt(sum(wu**2 for wu in weighted_uncertainties) / len(weighted_uncertainties))
        raw_instability = rms
        score = round(max(0.0, min(1.0, 1.0 - raw_instability)), 4)

        n_total = len(weighted_uncertainties)
        if score >= 0.8:
            reason = f"Consistent performance across {n_total} traces."
        elif score >= 0.5:
            reason = f"Moderate instability detected across {n_total} traces."
        else:
            reason = f"High instability across {n_total} traces; multiple signals compound."

        return MetricResult(
            score=score,
            reason=reason,
            metadata={
                "total_traces_in_session": len(traces),
                "traces_evaluated": n_total,
                "raw_instability": round(raw_instability, 4),
                "signal_weights": weights,
                "per_trace_signals": per_trace_details,
                "aggregation": {
                    "method": "weighted_rms",
                    "rms_value": round(rms, 4),
                },
            },
        )

"""StepEfficiency metric -- server-side implementation.

Evaluates how efficiently (minimally) an agent executed a task. Uses a
two-stage LLM judge approach:

1. **Extract** the user's original goal from the trace.
2. **Score** how efficiently the agent executed it (0-1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.evals.metrics import register_metric
from app.core.evals.metrics.base import BaseMetric, MetricResult
from app.core.evals.metrics.trace.step_efficiency.schema import (
    EfficiencyVerdict,
    Task,
)
from app.core.evals.metrics.trace.step_efficiency.template import (
    StepEfficiencyTemplate,
)

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.llm.engine import LLMEngine


@register_metric("step_efficiency")
class StepEfficiencyMetric(BaseMetric):
    """Measures how efficiently the agent executed the task with minimal steps."""

    name = "step_efficiency"
    description = "Evaluates how efficiently the agent executed the task with minimal unnecessary steps."
    category = "trace"
    threshold = 0.5
    prompt_description = (
        "Two-stage LLM judge: (1) extract the user's original goal from the trace, "
        "(2) score how efficiently the agent achieved it based on minimality of actions, "
        "penalizing redundant steps, unnecessary tool calls, and speculative work."
    )

    @classmethod
    def get_prompt_preview(cls) -> dict[str, str]:
        """Return actual prompt texts with sample data for preview."""
        return StepEfficiencyTemplate.get_prompt_preview()

    async def evaluate(
        self,
        trace: Trace,
        llm: LLMEngine,
        *,
        threshold: float | None = None,
        model: str | None = None,
        session_traces: list[Trace] | None = None,
    ) -> MetricResult:
        """Score a trace using this metric."""
        effective_threshold = threshold if threshold is not None else self.threshold

        trace_dict = trace.model_dump(mode="json")
        extract_prompt = StepEfficiencyTemplate.extract_task_from_trace(trace_dict)
        extraction = await llm.generate_structured(
            prompt=extract_prompt,
            response_schema=Task,
            model=model,
        )

        efficiency_prompt = StepEfficiencyTemplate.get_execution_efficiency(
            task=extraction.task,
            trace=trace_dict,
        )
        verdict = await llm.generate_structured(
            prompt=efficiency_prompt,
            response_schema=EfficiencyVerdict,
            model=model,
        )

        return MetricResult(
            score=verdict.score,
            reason=verdict.reason,
            metadata={
                "task": extraction.task,
                "threshold": effective_threshold,
                "success": verdict.score >= effective_threshold,
            },
        )

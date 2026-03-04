"""TaskCompletion metric -- server-side implementation.

Evaluates whether an agentic workflow actually accomplished the user's
stated objective.  Uses a two-stage LLM judge approach:

1. **Extract** the task and factual outcome from the trace.
2. **Score** how well the outcome fulfils the task (0-1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.evals.metrics import register_metric
from app.core.evals.metrics.base import BaseMetric, MetricResult
from app.core.evals.metrics.trace.task_completion.schema import (
    TaskAndOutcome,
    TaskCompletionVerdict,
)
from app.core.evals.metrics.trace.task_completion.template import TaskCompletionTemplate

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.llm.engine import LLMEngine


@register_metric("task_completion")
class TaskCompletionMetric(BaseMetric):
    """Measures how completely an agent fulfilled the user's request."""

    name = "task_completion"
    description = "Evaluates whether the agent accomplished the user's stated objective."
    category = "trace"
    threshold = 0.5
    prompt_description = (
        "Two-stage LLM judge: (1) extract the user's task and the agent's factual outcome "
        "from the trace, (2) score how well the outcome fulfills the task on a 0-1 scale."
    )

    @classmethod
    def get_prompt_preview(cls) -> dict[str, str]:
        """Return actual prompt texts with sample data for preview."""
        return TaskCompletionTemplate.get_prompt_preview()

    async def evaluate(
        self,
        trace: Trace,
        llm: LLMEngine,
        *,
        threshold: float | None = None,
        model: str | None = None,
    ) -> MetricResult:
        """Score a trace using this metric."""
        effective_threshold = threshold if threshold is not None else self.threshold

        trace_dict = trace.model_dump(mode="json")
        extract_prompt = TaskCompletionTemplate.extract_task_and_outcome(trace_dict)
        extraction = await llm.generate_structured(
            prompt=extract_prompt,
            response_schema=TaskAndOutcome,
            model=model,
        )

        verdict_prompt = TaskCompletionTemplate.generate_verdict(
            task=extraction.task,
            actual_outcome=extraction.outcome,
        )
        verdict = await llm.generate_structured(
            prompt=verdict_prompt,
            response_schema=TaskCompletionVerdict,
            model=model,
        )

        return MetricResult(
            score=verdict.verdict,
            reason=verdict.reason,
            metadata={
                "task": extraction.task,
                "outcome": extraction.outcome,
                "threshold": effective_threshold,
                "success": verdict.verdict >= effective_threshold,
            },
        )

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
from app.core.evals.metrics.task_completion.schema import (
    TaskAndOutcome,
    TaskCompletionVerdict,
)
from app.core.evals.metrics.task_completion.template import TaskCompletionTemplate

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.providers.base import AbstractLLMProvider


@register_metric("task_completion")
class TaskCompletionMetric(BaseMetric):
    """Measures how completely an agent fulfilled the user's request."""

    name = "task_completion"
    threshold = 0.5

    async def evaluate(
        self,
        trace: Trace,
        provider: AbstractLLMProvider,
        *,
        threshold: float | None = None,
    ) -> MetricResult:
        """Run the two-stage evaluation and return a scored result.

        Args:
            trace: The full trace with spans.
            provider: LLM provider for judge calls.
            threshold: Optional override for the pass/fail threshold.
        """
        effective_threshold = threshold if threshold is not None else self.threshold

        # Stage 1: Extract the task and outcome from the trace.
        trace_dict = trace.model_dump(mode="json")
        extract_prompt = TaskCompletionTemplate.extract_task_and_outcome(trace_dict)
        extraction = await provider.generate_structured(
            prompt=extract_prompt,
            response_schema=TaskAndOutcome,
        )

        # Stage 2: Judge how well the outcome matches the task.
        verdict_prompt = TaskCompletionTemplate.generate_verdict(
            task=extraction.task,
            actual_outcome=extraction.outcome,
        )
        verdict = await provider.generate_structured(
            prompt=verdict_prompt,
            response_schema=TaskCompletionVerdict,
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

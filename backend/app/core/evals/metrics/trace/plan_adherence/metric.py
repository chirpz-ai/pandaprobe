"""PlanAdherence metric -- server-side implementation.

Evaluates how closely the agent followed its declared plan during execution.
Uses a three-stage LLM judge approach:

1. **Extract** the user's task from the trace (reuses step_efficiency).
2. **Extract** the plan from the trace.
3. **Score** adherence (or return 1.0 if no plan found).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.evals.metrics import register_metric
from app.core.evals.metrics.base import BaseMetric, MetricResult
from app.core.evals.metrics.trace.plan_adherence.schema import (
    AgentPlan,
    PlanAdherenceScore,
)
from app.core.evals.metrics.trace.plan_adherence.template import (
    PlanAdherenceTemplate,
)
from app.core.evals.metrics.trace.step_efficiency.schema import Task
from app.core.evals.metrics.trace.step_efficiency.template import (
    StepEfficiencyTemplate,
)

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.llm.engine import LLMEngine


@register_metric("plan_adherence")
class PlanAdherenceMetric(BaseMetric):
    """Measures how closely the agent followed its declared plan during execution."""

    name = "plan_adherence"
    description = "Evaluates how closely the agent followed its declared plan during execution."
    category = "trace"
    threshold = 0.5
    prompt_description = (
        "Three-stage LLM judge: (1) extract the user's task from the trace, (2) extract "
        "the agent's explicit or implied plan from reasoning fields, (3) score how strictly "
        "the execution followed the declared plan, checking step order and completeness."
    )

    @classmethod
    def get_prompt_preview(cls) -> dict[str, str]:
        """Return actual prompt texts with sample data for preview."""
        return PlanAdherenceTemplate.get_prompt_preview()

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

        # Stage 1: Extract task from trace (reuse step_efficiency)
        task_prompt = StepEfficiencyTemplate.extract_task_from_trace(trace_dict)
        task_extraction = await llm.generate_structured(
            prompt=task_prompt,
            response_schema=Task,
            model=model,
        )
        user_task = task_extraction.task

        # Stage 2: Extract plan from trace
        plan_prompt = PlanAdherenceTemplate.extract_plan_from_trace(trace_dict)
        plan_extraction = await llm.generate_structured(
            prompt=plan_prompt,
            response_schema=AgentPlan,
            model=model,
        )
        plan = plan_extraction.plan

        # Stage 3: If plan is empty, return score=1.0
        if not plan:
            return MetricResult(
                score=1.0,
                reason="No plan found in trace",
                metadata={
                    "task": user_task,
                    "plan": [],
                    "threshold": effective_threshold,
                    "success": True,
                },
            )

        # Stage 4: Score adherence
        agent_plan_str = json.dumps(plan, indent=2)
        adherence_prompt = PlanAdherenceTemplate.evaluate_adherence(
            user_task=user_task,
            agent_plan=agent_plan_str,
            execution_trace=trace_dict,
        )
        verdict = await llm.generate_structured(
            prompt=adherence_prompt,
            response_schema=PlanAdherenceScore,
            model=model,
        )

        return MetricResult(
            score=verdict.score,
            reason=verdict.reason,
            metadata={
                "task": user_task,
                "plan": plan,
                "threshold": effective_threshold,
                "success": verdict.score >= effective_threshold,
            },
        )

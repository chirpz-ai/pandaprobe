"""PlanQuality metric -- server-side implementation.

Evaluates the intrinsic quality, completeness, and optimality of the agent's plan.
Uses a three-stage LLM judge approach:

1. **Extract** the user's task from the trace (reuses step_efficiency).
2. **Extract** the plan from the trace (reuses plan_adherence).
3. **Score** plan quality (or return 1.0 if no plan found).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.evals.metrics import register_metric
from app.core.evals.metrics.base import BaseMetric, MetricResult
from app.core.evals.metrics.trace.plan_adherence.schema import AgentPlan
from app.core.evals.metrics.trace.plan_adherence.template import (
    PlanAdherenceTemplate,
)
from app.core.evals.metrics.trace.plan_quality.schema import PlanQualityScore
from app.core.evals.metrics.trace.plan_quality.template import (
    PlanQualityTemplate,
)
from app.core.evals.metrics.trace.step_efficiency.schema import Task
from app.core.evals.metrics.trace.step_efficiency.template import (
    StepEfficiencyTemplate,
)

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.llm.engine import LLMEngine


@register_metric("plan_quality")
class PlanQualityMetric(BaseMetric):
    """Measures the intrinsic quality, completeness, and optimality of the agent's plan."""

    name = "plan_quality"
    description = "Evaluates the intrinsic quality, completeness, and optimality of the agent's plan."
    category = "trace"
    threshold = 0.5
    prompt_description = (
        "Three-stage LLM judge: (1) extract the user's task from the trace, (2) extract "
        "the agent's plan from reasoning fields, (3) score the plan's intrinsic quality "
        "based on completeness, logical coherence, optimality, and alignment with the task."
    )

    @classmethod
    def get_prompt_preview(cls) -> dict[str, str]:
        """Return actual prompt texts with sample data for preview."""
        return PlanQualityTemplate.get_prompt_preview()

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

        # Stage 1: Extract task from trace (reuse step_efficiency)
        task_prompt = StepEfficiencyTemplate.extract_task_from_trace(trace_dict)
        task_extraction = await llm.generate_structured(
            prompt=task_prompt,
            response_schema=Task,
            model=model,
        )
        user_task = task_extraction.task

        # Stage 2: Extract plan from trace (reuse plan_adherence)
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

        # Stage 4: Score plan quality
        agent_plan_str = json.dumps(plan, indent=2)
        quality_prompt = PlanQualityTemplate.evaluate_plan_quality(
            user_task=user_task,
            agent_plan=agent_plan_str,
        )
        verdict = await llm.generate_structured(
            prompt=quality_prompt,
            response_schema=PlanQualityScore,
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

"""ToolCorrectness metric -- server-side implementation.

Evaluates whether an AI agent selected the right tools for its task.
Uses a two-stage LLM judge approach:

1. **Extract** tool usage context from the trace (user input, tools called,
   available tools).
2. **Score** tool selection quality (0-1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.evals.metrics import register_metric
from app.core.evals.metrics.base import BaseMetric, MetricResult
from app.core.evals.metrics.trace.tool_correctness.schema import (
    ToolSelectionScore,
    ToolUsageContext,
)
from app.core.evals.metrics.trace.tool_correctness.template import (
    ToolCorrectnessTemplate,
)

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.llm.engine import LLMEngine


@register_metric("tool_correctness")
class ToolCorrectnessMetric(BaseMetric):
    """Measures whether the agent selected appropriate tools for the task."""

    name = "tool_correctness"
    description = "Evaluates whether the agent selected appropriate tools for the task."
    category = "trace"
    threshold = 0.5

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
        extract_prompt = ToolCorrectnessTemplate.extract_tool_usage(trace_dict)
        context = await llm.generate_structured(
            prompt=extract_prompt,
            response_schema=ToolUsageContext,
            model=model,
        )

        score_prompt = ToolCorrectnessTemplate.score_tool_selection(
            user_input=context.user_input,
            tools_called=context.tools_called,
            available_tools=context.available_tools,
        )
        verdict = await llm.generate_structured(
            prompt=score_prompt,
            response_schema=ToolSelectionScore,
            model=model,
        )

        return MetricResult(
            score=verdict.score,
            reason=verdict.reason,
            metadata={
                "user_input": context.user_input,
                "tools_called": context.tools_called,
                "available_tools": context.available_tools,
                "threshold": effective_threshold,
                "success": verdict.score >= effective_threshold,
            },
        )

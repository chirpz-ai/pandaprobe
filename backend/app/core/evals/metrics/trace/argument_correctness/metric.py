"""ArgumentCorrectness metric -- server-side implementation.

Evaluates whether tool call arguments/parameters were correctly specified
for the task. Uses a three-stage LLM judge approach:

1. **Extract** user input and all tool calls (name, parameters, reasoning).
2. **Verdict** per-call: yes/no + optional reason.
3. **Reason** overall explanation from score and incorrect-call reasons.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.evals.metrics import register_metric
from app.core.evals.metrics.base import BaseMetric, MetricResult
from app.core.evals.metrics.trace.argument_correctness.schema import (
    ArgumentCorrectnessReason,
    ArgumentVerdicts,
    ToolCallContext,
)
from app.core.evals.metrics.trace.argument_correctness.template import (
    ArgumentCorrectnessTemplate,
)

if TYPE_CHECKING:
    from app.core.traces.entities import Trace
    from app.infrastructure.llm.engine import LLMEngine


@register_metric("argument_correctness")
class ArgumentCorrectnessMetric(BaseMetric):
    """Measures whether tool call arguments were correctly specified."""

    name = "argument_correctness"
    description = "Evaluates whether tool call arguments were correctly specified for the task."
    category = "trace"
    threshold = 0.5
    prompt_description = (
        "Three-stage LLM judge: (1) extract user input and tool calls with parameters from "
        "the trace, (2) generate a per-tool-call yes/no verdict on whether arguments correctly "
        "address the task, (3) compute score as correct/total and produce an overall explanation."
    )

    @classmethod
    def get_prompt_preview(cls) -> dict[str, str]:
        """Return actual prompt texts with sample data for preview."""
        return ArgumentCorrectnessTemplate.get_prompt_preview()

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

        # Stage 1: Extract tool call context from trace
        extract_prompt = ArgumentCorrectnessTemplate.extract_tool_calls(trace_dict)
        extraction = await llm.generate_structured(
            prompt=extract_prompt,
            response_schema=ToolCallContext,
            model=model,
        )

        tool_calls = extraction.tool_calls or []
        user_input = extraction.user_input or ""

        # No tool calls: perfect score
        if not tool_calls:
            return MetricResult(
                score=1.0,
                reason="No tool calls in trace; nothing to evaluate.",
                metadata={
                    "user_input": user_input,
                    "verdicts": [],
                    "threshold": effective_threshold,
                    "success": True,
                },
            )

        # Stage 2: Generate per-call verdicts
        verdicts_prompt = ArgumentCorrectnessTemplate.generate_verdicts(
            user_input=user_input,
            tool_calls=tool_calls,
        )
        verdicts_result = await llm.generate_structured(
            prompt=verdicts_prompt,
            response_schema=ArgumentVerdicts,
            model=model,
        )

        verdicts = verdicts_result.verdicts or []
        total_verdicts = len(verdicts)
        correct_count = sum(1 for v in verdicts if v.verdict == "yes")
        score = min(correct_count / total_verdicts, 1.0) if total_verdicts > 0 else 1.0

        # Stage 3: Generate overall reason
        incorrect_reasons = [v.reason or "No reason provided" for v in verdicts if v.verdict == "no"]
        reason_prompt = ArgumentCorrectnessTemplate.generate_reason(
            incorrect_reasons=incorrect_reasons,
            user_input=user_input,
            score=score,
        )
        reason_result = await llm.generate_structured(
            prompt=reason_prompt,
            response_schema=ArgumentCorrectnessReason,
            model=model,
        )

        verdicts_metadata = [{"verdict": v.verdict, "reason": v.reason} for v in verdicts]

        return MetricResult(
            score=score,
            reason=reason_result.reason,
            metadata={
                "user_input": user_input,
                "verdicts": verdicts_metadata,
                "threshold": effective_threshold,
                "success": score >= effective_threshold,
            },
        )

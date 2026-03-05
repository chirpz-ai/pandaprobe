"""Pydantic schemas for the ArgumentCorrectness metric.

These are used as response_format when calling the judge LLM so
that the output is always machine-parseable.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ToolCallContext(BaseModel):
    """Extracted from the trace by the first LLM call."""

    user_input: str = Field(description="The user's original task")
    tool_calls: list[dict] = Field(description="Tool calls with name, parameters, and reasoning")


class ArgumentCorrectnessVerdict(BaseModel):
    """Per-tool-call verdict from the judge."""

    verdict: Literal["yes", "no"] = Field(description="Whether arguments are correct")
    reason: str | None = Field(
        default=None,
        description="Explanation if verdict is no",
    )


class ArgumentVerdicts(BaseModel):
    """Aggregated per-call verdicts from the judge."""

    verdicts: list[ArgumentCorrectnessVerdict]


class ArgumentCorrectnessReason(BaseModel):
    """Overall explanation for the final score."""

    reason: str = Field(description="Overall explanation for the score")

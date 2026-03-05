"""Pydantic schemas for the LLM judge's structured responses.

These are used as ``response_format`` when calling the judge LLM so
that the output is always machine-parseable.
"""

from pydantic import BaseModel, Field


class TaskAndOutcome(BaseModel):
    """Extracted from the trace by the first LLM call."""

    task: str = Field(description="The user's objective or goal")
    outcome: str = Field(description="Factual description of what the system did")


class TaskCompletionVerdict(BaseModel):
    """The judge's final verdict on task completion."""

    verdict: float = Field(ge=0.0, le=1.0, description="Score between 0 and 1")
    reason: str | None = Field(default=None, description="One-sentence reasoning")

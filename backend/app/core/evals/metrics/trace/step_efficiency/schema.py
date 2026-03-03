"""Pydantic schemas for the StepEfficiency metric's LLM judge responses."""

from pydantic import BaseModel, Field


class Task(BaseModel):
    """Extracted from the trace by the first LLM call."""

    task: str = Field(description="The user's original goal extracted from the trace")


class EfficiencyVerdict(BaseModel):
    """The judge's verdict on execution efficiency."""

    score: float = Field(ge=0.0, le=1.0, description="Efficiency score")
    reason: str = Field(description="Explanation of efficiency assessment")

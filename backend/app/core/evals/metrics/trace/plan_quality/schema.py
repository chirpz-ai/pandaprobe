"""Pydantic schemas for the PlanQuality metric's LLM judge responses."""

from pydantic import BaseModel, Field


class PlanQualityScore(BaseModel):
    """LLM judge's plan quality score and explanation."""

    score: float = Field(ge=0.0, le=1.0, description="Quality of the agent's plan")
    reason: str = Field(description="Explanation of quality assessment")

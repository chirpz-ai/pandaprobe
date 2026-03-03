"""Pydantic schemas for the PlanAdherence metric's LLM judge responses."""

from pydantic import BaseModel, Field


class AgentPlan(BaseModel):
    """Plan steps extracted from an agent trace."""

    plan: list[str] = Field(description="Ordered list of plan steps extracted from trace")


class PlanAdherenceScore(BaseModel):
    """LLM judge's adherence score and explanation."""

    score: float = Field(ge=0.0, le=1.0, description="How closely execution followed the plan")
    reason: str = Field(description="Explanation of adherence assessment")

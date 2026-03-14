"""Pydantic schemas for the confidence LLM judge's structured responses."""

from pydantic import BaseModel, Field


class ConfidenceVerdict(BaseModel):
    """LLM judge's assessment of agent confidence within a trace."""

    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reason: str | None = Field(default=None, description="One-sentence explanation")

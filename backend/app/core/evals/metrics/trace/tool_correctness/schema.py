"""Pydantic schemas for the tool_correctness LLM judge's structured responses.

These are used as response_format when calling the judge LLM so
that the output is always machine-parseable.
"""

from pydantic import BaseModel, Field


class ToolUsageContext(BaseModel):
    """Extracted from the trace: what user wanted and what tools were used."""

    user_input: str = Field(description="The user's original task/goal")
    tools_called: list[dict] = Field(description="List of tool calls with name and parameters")
    available_tools: list[dict] = Field(description="List of available tools with name and description")


class ToolSelectionScore(BaseModel):
    """LLM judge's assessment of tool selection quality."""

    score: float = Field(ge=0.0, le=1.0, description="Tool selection quality score")
    reason: str = Field(description="Explanation of the score")

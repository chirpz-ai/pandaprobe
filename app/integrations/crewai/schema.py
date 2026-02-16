"""Pydantic schemas for CrewAI trace payloads.

CrewAI organises work as **Crews → Tasks → Steps**.  Each task is
assigned to an agent, and steps within a task represent tool calls
or LLM invocations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrewAITokenUsage(BaseModel):
    """Token consumption for a single LLM step."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class CrewAIStep(BaseModel):
    """A single step (tool or LLM call) within a CrewAI task."""

    name: str = "step"
    type: str = "llm"
    input: Any | None = None
    output: Any | None = None
    error: str | None = None
    model: str | None = None
    token_usage: CrewAITokenUsage | None = None
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None


class CrewAITask(BaseModel):
    """A task executed by a CrewAI agent."""

    description: str = "task"
    agent: str | None = None
    input: Any | None = None
    output: Any | None = None
    status: str | None = None
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None
    steps: list[CrewAIStep] = Field(default_factory=list)


class CrewAIMeta(BaseModel):
    """Metadata about the Crew itself."""

    id: str | None = None
    name: str = "crewai-crew"


class CrewAITrace(BaseModel):
    """Top-level CrewAI execution trace envelope."""

    crew: CrewAIMeta = Field(default_factory=CrewAIMeta)
    agents: list[dict[str, Any]] = Field(default_factory=list)
    tasks: list[CrewAITask] = Field(default_factory=list)
    input: Any | None = None
    output: Any | None = None
    status: str | None = None
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None

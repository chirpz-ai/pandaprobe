"""Pydantic schemas for LangChain callback payloads.

LangChain's tracing callbacks (``BaseCallbackHandler``) produce *Run*
objects.  These schemas formalise the payload the Opentracer API
expects when a client sends LangChain-format traces.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LangChainTokenUsage(BaseModel):
    """Token usage reported by a LangChain LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LangChainRunExtra(BaseModel):
    """Extra metadata attached to a LangChain run."""

    invocation_params: dict[str, Any] = Field(default_factory=dict)
    token_usage: LangChainTokenUsage | None = None


class LangChainRun(BaseModel):
    """A single LangChain *Run* node.

    Runs form a tree via ``child_runs``.  The root run represents the
    top-level chain/agent invocation.
    """

    name: str = "unnamed"
    run_type: str = "chain"
    inputs: dict[str, Any] | Any | None = None
    outputs: dict[str, Any] | Any | None = None
    error: str | None = None
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None
    extra: LangChainRunExtra = Field(default_factory=LangChainRunExtra)
    child_runs: list[LangChainRun] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

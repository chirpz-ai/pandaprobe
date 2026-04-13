"""Pure domain entities for Traces and Spans.

Naming follows OpenTelemetry conventions where applicable so that
exported data can be correlated with OTel-based tooling.  These
models have **zero** infrastructure dependencies.
"""

import dataclasses
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus


class Span(BaseModel):
    """A single unit of work inside a trace.

    Spans form a tree: the root span has ``parent_span_id=None``,
    and every other span points to its parent.
    """

    span_id: UUID
    trace_id: UUID
    parent_span_id: UUID | None = None
    name: str = Field(min_length=1, max_length=512)
    kind: SpanKind = SpanKind.OTHER
    status: SpanStatusCode = SpanStatusCode.UNSET
    input: Any | None = None
    output: Any | None = None
    model: str | None = Field(default=None, max_length=255, description="LLM model name if applicable")
    token_usage: dict[str, Any] | None = Field(
        default=None,
        description="Token counts, e.g. {'prompt_tokens': 10, 'completion_tokens': 20}",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None
    error: str | None = None
    completion_start_time: datetime | None = None
    model_parameters: dict[str, Any] | None = None
    cost: dict[str, float] | None = None


class Trace(BaseModel):
    """A complete execution trace for an agentic workflow.

    A trace is the top-level container.  It groups one or more spans
    that together describe a single end-to-end agent run.
    """

    trace_id: UUID
    project_id: UUID
    name: str = Field(min_length=1, max_length=512)
    status: TraceStatus = TraceStatus.PENDING
    input: Any | None = None
    output: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None
    session_id: str | None = Field(default=None, max_length=255)
    user_id: str | None = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=list)
    environment: str | None = Field(default=None, max_length=255)
    release: str | None = Field(default=None, max_length=255)
    spans: list[Span] = Field(default_factory=list)


@dataclasses.dataclass(frozen=True, slots=True)
class TraceDetail:
    """A Trace bundled with its aggregated span statistics."""

    trace: Trace
    total_tokens: int
    total_cost: float

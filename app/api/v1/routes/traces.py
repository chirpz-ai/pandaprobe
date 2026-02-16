"""Routes for trace ingestion and retrieval.

Two ingestion paths:
- ``POST /traces`` -- accepts the universal Opentracer format.
- ``POST /traces/ingest/{source}`` -- accepts a framework-specific
  payload (e.g. ``langchain``, ``crewai``) and normalises it via the
  integration transformer.

Read endpoints query the database directly.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_org
from app.core.identity.entities import Organization
from app.core.traces.entities import Span, Trace
from app.infrastructure.db.engine import get_db_session
from app.integrations import get_integration, list_integrations
from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus
from app.services.trace_service import TraceService

router = APIRouter(prefix="/traces", tags=["traces"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class SpanCreate(BaseModel):
    """Schema for a span inside a trace-ingestion request."""

    span_id: UUID = Field(default_factory=uuid4)
    parent_span_id: UUID | None = None
    name: str = Field(min_length=1, max_length=512)
    kind: SpanKind = SpanKind.OTHER
    status: SpanStatusCode = SpanStatusCode.UNSET
    input: Any | None = None
    output: Any | None = None
    model: str | None = None
    token_usage: dict[str, int] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None


class TraceCreate(BaseModel):
    """Schema for the ``POST /traces`` request body."""

    trace_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=512)
    status: TraceStatus = TraceStatus.COMPLETED
    input: Any | None = None
    output: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None
    spans: list[SpanCreate] = Field(default_factory=list)


class TraceAccepted(BaseModel):
    """Response body for a successfully enqueued trace."""

    trace_id: UUID
    task_id: str


class SpanResponse(BaseModel):
    """Public span representation."""

    span_id: UUID
    trace_id: UUID
    parent_span_id: UUID | None
    name: str
    kind: SpanKind
    status: SpanStatusCode
    input: Any | None
    output: Any | None
    model: str | None
    token_usage: dict[str, int] | None
    metadata: dict[str, Any]
    started_at: str
    ended_at: str | None


class TraceResponse(BaseModel):
    """Public trace representation (single-item detail)."""

    trace_id: UUID
    org_id: UUID
    name: str
    status: TraceStatus
    input: Any | None
    output: Any | None
    metadata: dict[str, Any]
    started_at: str
    ended_at: str | None
    spans: list[SpanResponse] = Field(default_factory=list)


class TraceListItem(BaseModel):
    """Lightweight trace summary used in list responses."""

    trace_id: UUID
    name: str
    status: TraceStatus
    started_at: str
    ended_at: str | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=202, response_model=TraceAccepted)
async def ingest_trace(
    body: TraceCreate,
    org: Organization = Depends(require_org),
) -> TraceAccepted:
    """Accept a trace payload for asynchronous persistence.

    The trace is validated, then pushed onto a Redis-backed task queue.
    The background worker will persist it to PostgreSQL.  Returns
    ``202 Accepted`` with the ``trace_id`` and Celery ``task_id``.
    """
    trace = Trace(
        trace_id=body.trace_id,
        org_id=org.id,
        name=body.name,
        status=body.status,
        input=body.input,
        output=body.output,
        metadata=body.metadata,
        started_at=body.started_at,
        ended_at=body.ended_at,
        spans=[
            Span(
                span_id=s.span_id,
                trace_id=body.trace_id,
                parent_span_id=s.parent_span_id,
                name=s.name,
                kind=s.kind,
                status=s.status,
                input=s.input,
                output=s.output,
                model=s.model,
                token_usage=s.token_usage,
                metadata=s.metadata,
                started_at=s.started_at,
                ended_at=s.ended_at,
            )
            for s in body.spans
        ],
    )

    task_id = TraceService.enqueue_trace(trace)
    return TraceAccepted(trace_id=trace.trace_id, task_id=task_id)


@router.get("/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: UUID,
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_db_session),
) -> TraceResponse:
    """Retrieve a single trace with all its spans."""
    svc = TraceService(session)
    trace = await svc.get_trace(trace_id, org.id)
    return _trace_to_response(trace)


@router.get("", response_model=list[TraceListItem])
async def list_traces(
    org: Organization = Depends(require_org),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TraceListItem]:
    """List traces for the authenticated organisation, newest first."""
    svc = TraceService(session)
    traces = await svc.list_traces(org.id, limit=limit, offset=offset)
    return [
        TraceListItem(
            trace_id=t.trace_id,
            name=t.name,
            status=t.status,
            started_at=t.started_at.isoformat(),
            ended_at=t.ended_at.isoformat() if t.ended_at else None,
        )
        for t in traces
    ]


@router.post("/ingest/{source}", status_code=202, response_model=TraceAccepted)
async def ingest_framework_trace(
    source: str,
    body: dict[str, Any],
    org: Organization = Depends(require_org),
) -> TraceAccepted:
    """Accept a framework-specific trace payload for normalisation and persistence.

    The ``source`` path parameter selects the integration transformer
    (e.g. ``langchain``, ``langgraph``, ``crewai``).  The raw payload
    is transformed into the universal Opentracer format, then enqueued.
    """
    try:
        transformer_cls = get_integration(source)
    except KeyError:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail=f"Unknown integration '{source}'. Available: {list_integrations()}",
        )

    transformer = transformer_cls()
    trace = transformer.transform(body, org_id=org.id)
    task_id = TraceService.enqueue_trace(trace)
    return TraceAccepted(trace_id=trace.trace_id, task_id=task_id)


class IntegrationListResponse(BaseModel):
    """Available framework integrations."""

    integrations: list[str]


@router.get("/integrations", response_model=IntegrationListResponse)
async def get_available_integrations() -> IntegrationListResponse:
    """List all registered framework integrations."""
    return IntegrationListResponse(integrations=list_integrations())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trace_to_response(trace: Trace) -> TraceResponse:
    return TraceResponse(
        trace_id=trace.trace_id,
        org_id=trace.org_id,
        name=trace.name,
        status=trace.status,
        input=trace.input,
        output=trace.output,
        metadata=trace.metadata,
        started_at=trace.started_at.isoformat(),
        ended_at=trace.ended_at.isoformat() if trace.ended_at else None,
        spans=[
            SpanResponse(
                span_id=s.span_id,
                trace_id=s.trace_id,
                parent_span_id=s.parent_span_id,
                name=s.name,
                kind=s.kind,
                status=s.status,
                input=s.input,
                output=s.output,
                model=s.model,
                token_usage=s.token_usage,
                metadata=s.metadata,
                started_at=s.started_at.isoformat(),
                ended_at=s.ended_at.isoformat() if s.ended_at else None,
            )
            for s in trace.spans
        ],
    )

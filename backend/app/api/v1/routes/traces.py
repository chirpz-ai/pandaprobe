"""Routes for trace ingestion and retrieval.

``POST /traces`` accepts the universal PandaProbe format, validates
the schema, resolves the project, and enqueues the trace for
background persistence.

Authentication: Bearer JWT (with ``X-Project-ID`` header) **or**
``X-API-Key`` with ``X-Project-Name``.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import require_project
from app.api.rate_limit import limiter
from app.api.v1.schemas import PaginatedResponse
from app.core.traces.entities import Span, Trace
from app.infrastructure.db.engine import get_db_session
from app.registry.constants import (
    AnalyticsGranularity,
    AnalyticsMetric,
    SortOrder,
    SpanKind,
    SpanStatusCode,
    TraceSortBy,
    TraceStatus,
)
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
    model: str | None = Field(default=None, max_length=255)
    token_usage: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None
    error: str | None = None
    completion_start_time: datetime | None = None
    model_parameters: dict[str, Any] | None = None
    cost: dict[str, float] | None = None


class SpanUpdate(BaseModel):
    """Partial-update schema for a span (all fields optional)."""

    name: str | None = Field(default=None, max_length=512)
    kind: SpanKind | None = None
    status: SpanStatusCode | None = None
    input: Any | None = Field(default=None)
    output: Any | None = Field(default=None)
    model: str | None = Field(default=None, max_length=255)
    token_usage: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    ended_at: datetime | None = None
    error: str | None = None
    completion_start_time: datetime | None = None
    model_parameters: dict[str, Any] | None = None
    cost: dict[str, float] | None = None


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
    session_id: str | None = Field(default=None, max_length=255)
    user_id: str | None = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=list)
    environment: str | None = Field(default=None, max_length=255)
    release: str | None = Field(default=None, max_length=255)
    spans: list[SpanCreate] = Field(default_factory=list, max_length=500)


class TraceUpdate(BaseModel):
    """Partial-update schema for a trace (all fields optional)."""

    name: str | None = Field(default=None, max_length=512)
    status: TraceStatus | None = None
    input: Any | None = Field(default=None)
    output: Any | None = Field(default=None)
    metadata: dict[str, Any] | None = None
    ended_at: datetime | None = None
    session_id: str | None = Field(default=None, max_length=255)
    user_id: str | None = Field(default=None, max_length=255)
    tags: list[str] | None = None
    environment: str | None = Field(default=None, max_length=255)
    release: str | None = Field(default=None, max_length=255)


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
    token_usage: dict[str, Any] | None
    metadata: dict[str, Any]
    started_at: str
    ended_at: str | None
    error: str | None
    completion_start_time: str | None
    model_parameters: dict[str, Any] | None
    cost: dict[str, float] | None
    latency_ms: float | None = None
    time_to_first_token_ms: float | None = None


class TraceResponse(BaseModel):
    """Public trace representation (single-item detail)."""

    trace_id: UUID
    project_id: UUID
    name: str
    status: TraceStatus
    input: Any | None
    output: Any | None
    metadata: dict[str, Any]
    started_at: str
    ended_at: str | None
    session_id: str | None
    user_id: str | None
    tags: list[str]
    environment: str | None = None
    release: str | None = None
    spans: list[SpanResponse] = Field(default_factory=list)


class TraceListItem(BaseModel):
    """Lightweight trace summary used in list responses."""

    trace_id: UUID
    name: str
    status: TraceStatus
    started_at: str
    ended_at: str | None
    session_id: str | None
    user_id: str | None
    tags: list[str]
    environment: str | None = None
    release: str | None = None
    latency_ms: float | None = None
    span_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


class SpansAccepted(BaseModel):
    """Response body for successfully added spans."""

    span_ids: list[UUID]


class BatchDeleteRequest(BaseModel):
    """Request body for bulk trace deletion."""

    trace_ids: list[UUID] = Field(min_length=1, max_length=500)


class BatchDeleteResponse(BaseModel):
    """Response for bulk trace deletion (count removed)."""

    deleted: int


class BatchTagsRequest(BaseModel):
    """Request body for bulk tag manipulation on traces."""

    trace_ids: list[UUID] = Field(min_length=1, max_length=500)
    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)


class BatchTagsResponse(BaseModel):
    """Response for bulk tag update (count of traces affected)."""

    updated: int


class AnalyticsBucket(BaseModel):
    """Time-bucketed trace volume, error, and latency statistics."""

    bucket: str
    trace_count: int = 0
    error_count: int = 0
    avg_latency_ms: float | None = None
    p50_latency_ms: float | None = None
    p90_latency_ms: float | None = None
    p99_latency_ms: float | None = None


class TokenCostBucket(BaseModel):
    """Time-bucketed token usage and cost aggregation."""

    bucket: str
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0


class TopModel(BaseModel):
    """LLM model ranked by call count within a time window."""

    model: str
    call_count: int
    total_tokens: int = 0
    total_cost: float = 0.0


class UserSummary(BaseModel):
    """Aggregated trace statistics for a single end-user."""

    user_id: str
    trace_count: int
    first_seen: str
    last_seen: str
    error_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=202, response_model=TraceAccepted)
@limiter.limit("100/minute")
async def ingest_trace(
    request: Request,
    body: TraceCreate,
    ctx: ApiContext = Depends(require_project),
) -> TraceAccepted:
    """Accept a trace payload for asynchronous persistence (upsert).

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`

    Rate limit: `100/min`
    """
    trace = Trace(
        trace_id=body.trace_id,
        project_id=ctx.project.id,
        name=body.name,
        status=body.status,
        input=body.input,
        output=body.output,
        metadata=body.metadata,
        started_at=body.started_at,
        ended_at=body.ended_at,
        session_id=body.session_id,
        user_id=body.user_id,
        tags=body.tags,
        environment=body.environment,
        release=body.release,
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
                error=s.error,
                completion_start_time=s.completion_start_time,
                model_parameters=s.model_parameters,
                cost=s.cost,
            )
            for s in body.spans
        ],
    )

    task_id = TraceService.enqueue_trace(trace)
    return TraceAccepted(trace_id=trace.trace_id, task_id=task_id)


@router.get("", response_model=PaginatedResponse[TraceListItem])
async def list_traces(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session_id: str | None = Query(default=None),
    status: TraceStatus | None = Query(default=None),
    user_id: str | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    name: str | None = Query(default=None),
    started_after: datetime | None = Query(default=None),
    started_before: datetime | None = Query(default=None),
    sort_by: TraceSortBy = Query(default=TraceSortBy.STARTED_AT),
    sort_order: SortOrder = Query(default=SortOrder.DESC),
) -> PaginatedResponse[TraceListItem]:
    """List traces for the current project with filtering, sorting, and stats.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)
    rows, total = await svc.list_traces(
        ctx.project.id,
        limit=limit,
        offset=offset,
        session_id=session_id,
        status=status,
        user_id=user_id,
        tags=tags,
        name=name,
        started_after=started_after,
        started_before=started_before,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    items = [_row_to_list_item(r) for r in rows]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/analytics", response_model=list[AnalyticsBucket] | list[TokenCostBucket] | list[TopModel])
async def get_analytics(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    metric: AnalyticsMetric = Query(default=AnalyticsMetric.VOLUME),
    granularity: AnalyticsGranularity = Query(default=AnalyticsGranularity.DAY),
    started_after: datetime = Query(...),
    started_before: datetime = Query(...),
) -> list[AnalyticsBucket] | list[TokenCostBucket] | list[TopModel]:
    """Time-series analytics for traces.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)

    if metric in (AnalyticsMetric.VOLUME, AnalyticsMetric.ERRORS, AnalyticsMetric.LATENCY):
        rows = await svc.get_trace_analytics(
            ctx.project.id,
            granularity,
            started_after,
            started_before,
        )
        return [
            AnalyticsBucket(
                bucket=r.bucket.isoformat() if r.bucket else "",
                trace_count=r.trace_count or 0,
                error_count=r.error_count or 0,
                avg_latency_ms=float(r.avg_latency_ms) if r.avg_latency_ms is not None else None,
                p50_latency_ms=float(r.p50_latency_ms) if r.p50_latency_ms is not None else None,
                p90_latency_ms=float(r.p90_latency_ms) if r.p90_latency_ms is not None else None,
                p99_latency_ms=float(r.p99_latency_ms) if r.p99_latency_ms is not None else None,
            )
            for r in rows
        ]

    if metric in (AnalyticsMetric.COST, AnalyticsMetric.TOKENS):
        rows = await svc.get_token_cost_analytics(
            ctx.project.id,
            granularity,
            started_after,
            started_before,
        )
        return [
            TokenCostBucket(
                bucket=r.bucket.isoformat() if r.bucket else "",
                total_tokens=int(r.total_tokens or 0),
                prompt_tokens=int(r.prompt_tokens or 0),
                completion_tokens=int(r.completion_tokens or 0),
                total_cost=float(r.total_cost or 0),
            )
            for r in rows
        ]

    rows = await svc.get_top_models(
        ctx.project.id,
        started_after,
        started_before,
    )
    return [
        TopModel(
            model=r.model,
            call_count=r.call_count or 0,
            total_tokens=int(r.total_tokens or 0),
            total_cost=float(r.total_cost or 0),
        )
        for r in rows
    ]


@router.get("/users", response_model=PaginatedResponse[UserSummary])
async def list_trace_users(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[UserSummary]:
    """List unique user_ids with trace statistics.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)
    rows, total = await svc.list_trace_users(ctx.project.id, limit=limit, offset=offset)
    items = [
        UserSummary(
            user_id=r.user_id,
            trace_count=r.trace_count,
            first_seen=r.first_seen.isoformat(),
            last_seen=r.last_seen.isoformat(),
            error_count=r.error_count or 0,
        )
        for r in rows
    ]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/batch/delete", response_model=BatchDeleteResponse)
async def batch_delete(
    body: BatchDeleteRequest,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> BatchDeleteResponse:
    """Delete multiple traces at once.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)
    count = await svc.batch_delete_traces(ctx.project.id, body.trace_ids)
    return BatchDeleteResponse(deleted=count)


@router.post("/batch/tags", response_model=BatchTagsResponse)
async def batch_tags(
    body: BatchTagsRequest,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> BatchTagsResponse:
    """Add or remove tags on multiple traces.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    if not body.add_tags and not body.remove_tags:
        return BatchTagsResponse(updated=0)

    svc = TraceService(session)
    count = await svc.batch_update_tags(
        ctx.project.id,
        body.trace_ids,
        add_tags=body.add_tags or None,
        remove_tags=body.remove_tags or None,
    )
    return BatchTagsResponse(updated=count)


# -- Parameterised /{trace_id} routes -----------------------------------------


@router.patch("/{trace_id}", response_model=TraceResponse)
async def update_trace(
    trace_id: UUID,
    body: TraceUpdate,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> TraceResponse:
    """Partially update a trace.

    Only fields present in the request body are touched.  Sending
    ``"session_id": null`` explicitly clears the field; omitting
    ``session_id`` entirely leaves it unchanged.  ``metadata`` is
    shallow-merged with existing values.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    fields = body.model_dump(exclude_unset=True)

    svc = TraceService(session)
    trace = await svc.update_trace(trace_id, ctx.project.id, **fields)
    return _trace_to_response(trace)


@router.post("/{trace_id}/spans", status_code=201, response_model=SpansAccepted)
async def add_spans(
    trace_id: UUID,
    body: list[SpanCreate] = Body(..., min_length=1, max_length=500),
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> SpansAccepted:
    """Add one or more spans to an existing trace (upsert).

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    spans = [
        Span(
            span_id=s.span_id,
            trace_id=trace_id,
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
            error=s.error,
            completion_start_time=s.completion_start_time,
            model_parameters=s.model_parameters,
            cost=s.cost,
        )
        for s in body
    ]

    svc = TraceService(session)
    await svc.add_spans(trace_id, ctx.project.id, spans)
    return SpansAccepted(span_ids=[s.span_id for s in spans])


@router.patch("/{trace_id}/spans/{span_id}", response_model=SpanResponse)
async def update_span(
    trace_id: UUID,
    span_id: UUID,
    body: SpanUpdate,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> SpanResponse:
    """Partially update a span on a trace.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    fields = body.model_dump(exclude_unset=True)

    svc = TraceService(session)
    span = await svc.update_span(span_id, trace_id, ctx.project.id, **fields)
    return _span_to_response(span)


@router.get("/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> TraceResponse:
    """Retrieve a single trace with all its spans.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)
    trace = await svc.get_trace(trace_id, ctx.project.id)
    return _trace_to_response(trace)


@router.delete("/{trace_id}", status_code=204)
async def delete_trace(
    trace_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a trace and all its spans.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)
    await svc.delete_trace(trace_id, ctx.project.id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _span_to_response(s: Any) -> SpanResponse:
    latency = None
    if s.started_at and s.ended_at:
        latency = (s.ended_at - s.started_at).total_seconds() * 1000

    ttft = None
    if s.started_at and s.completion_start_time:
        ttft = (s.completion_start_time - s.started_at).total_seconds() * 1000

    return SpanResponse(
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
        error=s.error,
        completion_start_time=(s.completion_start_time.isoformat() if s.completion_start_time else None),
        model_parameters=s.model_parameters,
        cost=s.cost,
        latency_ms=latency,
        time_to_first_token_ms=ttft,
    )


def _row_to_list_item(r: Any) -> TraceListItem:
    """Map a joined Row (trace + span_stats) to a TraceListItem."""
    return TraceListItem(
        trace_id=r.trace_id,
        name=r.name,
        status=TraceStatus(r.status),
        started_at=r.started_at.isoformat(),
        ended_at=r.ended_at.isoformat() if r.ended_at else None,
        session_id=r.session_id,
        user_id=r.user_id,
        tags=list(r.tags) if r.tags else [],
        environment=r.environment if hasattr(r, "environment") else None,
        release=r.release if hasattr(r, "release") else None,
        latency_ms=float(r.latency_ms) if r.latency_ms is not None else None,
        span_count=int(r.span_count) if r.span_count is not None else 0,
        total_tokens=int(r.total_tokens) if r.total_tokens is not None else 0,
        total_cost=float(r.total_cost) if r.total_cost is not None else 0.0,
    )


def _trace_to_response(trace: Trace) -> TraceResponse:
    return TraceResponse(
        trace_id=trace.trace_id,
        project_id=trace.project_id,
        name=trace.name,
        status=trace.status,
        input=trace.input,
        output=trace.output,
        metadata=trace.metadata,
        started_at=trace.started_at.isoformat(),
        ended_at=trace.ended_at.isoformat() if trace.ended_at else None,
        session_id=trace.session_id,
        user_id=trace.user_id,
        tags=trace.tags,
        environment=trace.environment,
        release=trace.release,
        spans=[_span_to_response(s) for s in trace.spans],
    )

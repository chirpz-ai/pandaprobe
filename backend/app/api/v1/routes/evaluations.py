"""Routes for evaluation runs, trace scores, and analytics.

Eval runs execute **asynchronously**: POST creates the job and returns
``202 Accepted``.  A Celery worker runs the metrics and writes trace
scores.  Use GET endpoints to poll progress or retrieve results.

Authentication: Bearer JWT (with ``X-Project-ID`` header) **or**
``X-API-Key`` with ``X-Project-Name``.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import require_project
from app.api.rate_limit import limiter
from app.api.v1.schemas import PaginatedResponse
from app.core.evals.metrics import get_metric_info, list_metrics
from app.infrastructure.db.engine import get_db_session
from app.registry.constants import (
    AnalyticsGranularity,
    EvaluationStatus,
    ScoreDataType,
    ScoreSource,
    ScoreStatus,
)
from app.services.eval_service import EvalService

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class EvalRunFilters(BaseModel):
    """Filters for selecting traces in an eval run."""

    date_from: str | None = None
    date_to: str | None = None
    status: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    tags: list[str] | None = None
    name: str | None = None


class CreateEvalRunRequest(BaseModel):
    """Payload for creating an eval run."""

    name: str | None = None
    metrics: list[str] = Field(min_length=1, description="Metric names to run")
    target_type: str = Field(default="TRACE")
    filters: EvalRunFilters = Field(default_factory=EvalRunFilters)
    sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    model: str | None = None


class EvalRunResponse(BaseModel):
    """Full eval run representation."""

    id: UUID
    project_id: UUID
    name: str | None
    target_type: str
    metric_names: list[str]
    filters: dict[str, Any]
    sampling_rate: float
    model: str | None
    status: EvaluationStatus
    total_traces: int
    evaluated_count: int
    failed_count: int
    error_message: str | None
    created_at: str
    completed_at: str | None


class TraceScoreResponse(BaseModel):
    """Single trace score."""

    id: UUID
    trace_id: UUID
    project_id: UUID
    name: str
    data_type: ScoreDataType
    value: str | None
    source: ScoreSource
    status: ScoreStatus
    eval_run_id: UUID | None
    author_user_id: str | None
    reason: str | None
    environment: str | None
    config_id: str | None
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class MetricInfo(BaseModel):
    """Summary info about an available metric."""

    name: str
    description: str
    category: str
    default_threshold: float


class MetricDetail(MetricInfo):
    """Extended info about a metric."""

    pass


class ProviderInfo(BaseModel):
    """Availability info for a single LLM provider."""

    key: str
    name: str
    description: str
    available: bool
    message: str


class ScoreSummaryItem(BaseModel):
    """Aggregated score summary for one metric."""

    metric_name: str
    avg_score: float
    count: int


class ScoreTrendItem(BaseModel):
    """Time-bucketed average score for a metric."""

    bucket: str | None
    metric_name: str
    avg_score: float
    count: int


class ScoreDistributionItem(BaseModel):
    """Histogram bucket for score distribution."""

    bucket: int
    bucket_min: float
    bucket_max: float
    count: int


# ---------------------------------------------------------------------------
# Metric discovery
# ---------------------------------------------------------------------------


@router.get("/metrics", response_model=list[MetricInfo])
async def get_available_metrics() -> list[MetricInfo]:
    """List all registered evaluation metrics with metadata."""
    names = list_metrics()
    return [MetricInfo(**get_metric_info(n)) for n in names]


@router.get("/metrics/{metric_name}", response_model=MetricDetail)
async def get_metric_detail(metric_name: str) -> MetricDetail:
    """Get detailed info about a specific metric."""
    info = get_metric_info(metric_name)
    return MetricDetail(**info)


@router.get("/providers", response_model=list[ProviderInfo])
async def get_available_providers() -> list[ProviderInfo]:
    """List LLM providers and their availability."""
    from app.infrastructure.llm.engine import LLMEngine

    engine = LLMEngine()
    return [ProviderInfo(**p) for p in engine.available_providers()]


# ---------------------------------------------------------------------------
# Eval runs
# ---------------------------------------------------------------------------


@router.post("/runs", status_code=202, response_model=EvalRunResponse)
@limiter.limit("50/minute")
async def create_eval_run(
    request: Request,
    body: CreateEvalRunRequest,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunResponse:
    """Create and execute an eval run.

    Rate limit: ``50/min``
    """
    svc = EvalService(session)
    filters_dict = body.filters.model_dump(exclude_none=True)
    run = await svc.create_eval_run(
        project_id=ctx.project.id,
        metric_names=body.metrics,
        filters=filters_dict,
        sampling_rate=body.sampling_rate,
        model=body.model,
        name=body.name,
        target_type=body.target_type,
    )
    return _run_to_response(run)


@router.get("/runs", response_model=PaginatedResponse[EvalRunResponse])
async def list_eval_runs(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    status: EvaluationStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[EvalRunResponse]:
    """List eval runs for the current project."""
    svc = EvalService(session)
    runs, total = await svc.list_eval_runs(ctx.project.id, status=status, limit=limit, offset=offset)
    return PaginatedResponse(
        items=[_run_to_response(r) for r in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
async def get_eval_run(
    run_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunResponse:
    """Get eval run detail with progress."""
    svc = EvalService(session)
    run = await svc.get_eval_run(run_id, ctx.project.id)
    return _run_to_response(run)


# ---------------------------------------------------------------------------
# Trace scores
# ---------------------------------------------------------------------------


@router.get("/trace-scores", response_model=PaginatedResponse[TraceScoreResponse])
async def list_trace_scores(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    trace_id: UUID | None = Query(default=None),
    metric_name: str | None = Query(default=None, alias="name"),
    source: ScoreSource | None = Query(default=None),
    data_type: ScoreDataType | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[TraceScoreResponse]:
    """List trace scores with filters."""
    svc = EvalService(session)
    scores, total = await svc.list_scores(
        ctx.project.id,
        name=metric_name,
        trace_id=trace_id,
        source=source,
        data_type=data_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(
        items=[_score_to_response(s) for s in scores],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/trace-scores/by-trace/{trace_id}", response_model=list[TraceScoreResponse])
async def get_scores_by_trace(
    trace_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> list[TraceScoreResponse]:
    """Get all scores for a specific trace."""
    svc = EvalService(session)
    scores = await svc.get_scores_for_trace(trace_id, ctx.project.id)
    return [_score_to_response(s) for s in scores]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get("/analytics/summary", response_model=list[ScoreSummaryItem])
async def get_analytics_summary(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> list[ScoreSummaryItem]:
    """Aggregated trace score summary per metric."""
    svc = EvalService(session)
    data = await svc.get_score_summary(ctx.project.id, date_from=date_from, date_to=date_to)
    return [ScoreSummaryItem(**d) for d in data]


@router.get("/analytics/trend", response_model=list[ScoreTrendItem])
async def get_analytics_trend(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    metric_name: str = Query(...),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    granularity: AnalyticsGranularity = Query(default=AnalyticsGranularity.DAY),
) -> list[ScoreTrendItem]:
    """Time series of average trace scores by metric."""
    svc = EvalService(session)
    data = await svc.get_score_trend(
        ctx.project.id,
        metric_name=metric_name,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
    )
    return [ScoreTrendItem(**d) for d in data]


@router.get("/analytics/distribution", response_model=list[ScoreDistributionItem])
async def get_analytics_distribution(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    metric_name: str = Query(...),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    buckets: int = Query(default=10, ge=1, le=100),
) -> list[ScoreDistributionItem]:
    """Histogram of trace score values for a metric."""
    svc = EvalService(session)
    data = await svc.get_score_distribution(
        ctx.project.id,
        metric_name,
        date_from=date_from,
        date_to=date_to,
        buckets=buckets,
    )
    return [ScoreDistributionItem(**d) for d in data]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_to_response(run) -> EvalRunResponse:
    return EvalRunResponse(
        id=run.id,
        project_id=run.project_id,
        name=run.name,
        target_type=run.target_type,
        metric_names=run.metric_names,
        filters=run.filters,
        sampling_rate=run.sampling_rate,
        model=run.model,
        status=run.status,
        total_traces=run.total_traces,
        evaluated_count=run.evaluated_count,
        failed_count=run.failed_count,
        error_message=run.error_message,
        created_at=run.created_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
    )


def _score_to_response(score) -> TraceScoreResponse:
    return TraceScoreResponse(
        id=score.id,
        trace_id=score.trace_id,
        project_id=score.project_id,
        name=score.name,
        data_type=score.data_type,
        value=score.value,
        source=score.source,
        status=score.status,
        eval_run_id=score.eval_run_id,
        author_user_id=score.author_user_id,
        reason=score.reason,
        environment=score.environment,
        config_id=score.config_id,
        metadata=score.metadata,
        created_at=score.created_at.isoformat(),
        updated_at=score.updated_at.isoformat(),
    )

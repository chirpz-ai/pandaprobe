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
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import require_project
from app.api.rate_limit import limiter
from app.api.v1.schemas import PaginatedResponse
from app.core.evals.entities import validate_score_value
from app.core.evals.metrics import (
    get_metric_info,
    get_metric_summary,
    get_session_metric_summary,
    list_metrics,
    list_session_metrics,
)
from app.infrastructure.db.engine import get_db_session
from app.registry.constants import (
    AnalyticsGranularity,
    EvaluationStatus,
    MonitorStatus,
    ScoreDataType,
    ScoreSource,
    ScoreStatus,
    TraceStatus,
)
from app.services.eval_service import EvalService

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


# ---------------------------------------------------------------------------
# Schemas -- Metrics
# ---------------------------------------------------------------------------


class PromptPreview(BaseModel):
    """Actual LLM prompt text for one evaluation stage, rendered with sample data."""

    stage: str
    prompt: str


class MetricSummary(BaseModel):
    """Lightweight metric info for the list endpoint."""

    name: str
    description: str
    category: str


class MetricInfo(MetricSummary):
    """Full metric info including threshold and prompt previews."""

    default_threshold: float
    prompt_preview: list[PromptPreview]


class ProviderInfo(BaseModel):
    """Availability info for a single LLM provider."""

    key: str
    name: str
    description: str
    available: bool
    message: str


# ---------------------------------------------------------------------------
# Schemas -- Eval runs
# ---------------------------------------------------------------------------


class EvalRunFilters(BaseModel):
    """Trace filters for a filtered eval run.

    These mirror the GET /traces query parameters so the frontend can
    reuse the same filter UI components.
    """

    date_from: str | None = Field(
        default=None,
        description="ISO 8601 datetime string (e.g. '2025-01-15T00:00:00Z'). Include traces started on or after this time.",
    )
    date_to: str | None = Field(
        default=None,
        description="ISO 8601 datetime string (e.g. '2025-02-01T00:00:00Z'). Include traces started before this time (exclusive).",
    )
    status: TraceStatus | None = Field(
        default=None,
        description="Trace status: PENDING, RUNNING, COMPLETED, or ERROR.",
    )
    session_id: str | None = Field(
        default=None,
        description="Exact session ID string. Only traces belonging to this session.",
    )
    user_id: str | None = Field(
        default=None,
        description="Exact user ID string. Only traces from this user.",
    )
    tags: list[str] | None = Field(
        default=None,
        description="List of tag strings (e.g. ['production', 'v2']). Traces matching ANY of these tags are included.",
    )
    name: str | None = Field(
        default=None,
        description="Substring match on trace name (case-insensitive). E.g. 'booking' matches 'Flight Booking Agent'.",
    )


class CreateEvalRunRequest(BaseModel):
    """Create a filtered eval run.

    The system resolves matching traces from the filters, optionally
    samples a fraction of them, then dispatches a background task to
    run the requested metrics asynchronously via an LLM judge.

    **Typical dashboard flow:**
    1. User selects metrics -> call ``GET /trace-runs/template?metric=task_completion``
    2. Dashboard renders the template as a form with editable filters
    3. User customizes filters/sampling -> frontend builds this request body
    4. Frontend calls ``POST /trace-runs`` with the final body
    """

    name: str | None = Field(
        default=None,
        description="Optional human-readable label for this run (e.g. 'Weekly prod eval').",
    )
    metrics: list[str] = Field(
        min_length=1,
        description="List of metric names to run. Use GET /evaluations/trace-metrics to see available names. Example: ['task_completion', 'tool_correctness'].",
    )
    filters: EvalRunFilters = Field(
        default_factory=EvalRunFilters,
        description="Trace filters to select which traces to evaluate. Omit or leave empty to evaluate all traces in the project.",
    )
    sampling_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Fraction of matching traces to evaluate (0.0 to 1.0). 1.0 = all matching traces, 0.1 = random 10%.",
    )
    model: str | None = Field(
        default=None,
        description="LLM model string override for the judge (e.g. 'openai/gpt-4o'). Null uses the system default.",
    )


class CreateBatchEvalRunRequest(BaseModel):
    """Create an eval run for an explicit list of trace IDs.

    Use this when the user has manually selected specific traces in the
    dashboard rather than using filter-based selection.
    """

    trace_ids: list[UUID] = Field(
        min_length=1,
        description="List of trace UUIDs to evaluate. Duplicates are removed automatically.",
    )
    metrics: list[str] = Field(
        min_length=1,
        description="List of metric names to run on each trace. Example: ['task_completion', 'step_efficiency'].",
    )
    name: str | None = Field(
        default=None,
        description="Optional human-readable label for this run.",
    )
    model: str | None = Field(
        default=None,
        description="LLM model string override for the judge. Null uses the system default.",
    )


class EvalRunResponse(BaseModel):
    """Full eval run representation used by both list and detail endpoints."""

    id: UUID
    name: str | None
    status: EvaluationStatus
    metric_names: list[str]
    total_traces: int
    evaluated_count: int
    failed_count: int
    created_at: str
    completed_at: str | None
    project_id: UUID
    target_type: str
    filters: dict[str, Any]
    sampling_rate: float
    model: str | None
    monitor_id: UUID | None
    error_message: str | None


class EvalRunTemplate(BaseModel):
    """Pre-filled template the dashboard renders as an editable form."""

    metric: MetricInfo
    filters: EvalRunFilters
    sampling_rate: float
    model: str | None


# ---------------------------------------------------------------------------
# Schemas -- Trace scores
# ---------------------------------------------------------------------------


class TraceScoreResponse(BaseModel):
    """Full trace score representation used by both list and detail endpoints."""

    id: UUID
    trace_id: UUID
    name: str
    value: str | None
    status: ScoreStatus
    source: ScoreSource
    created_at: str
    project_id: UUID
    data_type: ScoreDataType
    eval_run_id: UUID | None
    author_user_id: str | None
    reason: str | None
    environment: str | None
    config_id: str | None
    metadata: dict[str, Any]
    updated_at: str


class CreateTraceScoreRequest(BaseModel):
    """Manually create a trace score (annotation or programmatic).

    Used by the dashboard for human annotations or by the SDK for
    programmatic score submission.
    """

    trace_id: UUID = Field(description="Trace UUID to attach the score to.")
    name: str = Field(description="Metric/score name (e.g. 'task_completion', 'quality', 'thumbs_up').")
    value: str = Field(
        description="Score value as string. For NUMERIC: '0.85', for BOOLEAN: 'true', for CATEGORICAL: 'PASS'."
    )
    data_type: ScoreDataType = Field(
        default=ScoreDataType.NUMERIC, description="Value type: NUMERIC, BOOLEAN, CATEGORICAL."
    )
    source: ScoreSource = Field(
        default=ScoreSource.ANNOTATION, description="Score origin: ANNOTATION (human) or PROGRAMMATIC (SDK)."
    )
    reason: str | None = Field(default=None, description="Optional explanation or annotation note.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata object.")

    @model_validator(mode="after")
    def _validate_value_for_data_type(self) -> "CreateTraceScoreRequest":
        """Reject invalid values at API layer so we return 422 instead of 500."""
        validate_score_value(self.value, self.data_type)
        return self


class UpdateTraceScoreRequest(BaseModel):
    """Editable fields for a trace score.

    All fields are optional -- only provided fields are updated.
    ``status`` is set to SUCCESS automatically on save, and
    ``source`` is changed to ANNOTATION to indicate human edit.
    ``updated_at`` is also set automatically.
    """

    value: str | None = Field(
        default=None, description="New score value (e.g. '0.9' for NUMERIC, 'true' for BOOLEAN)."
    )
    reason: str | None = Field(default=None, description="Updated reason or annotation note.")
    metadata: dict[str, Any] | None = Field(default=None, description="Updated metadata object (replaces existing).")


# ---------------------------------------------------------------------------
# Schemas -- Analytics
# ---------------------------------------------------------------------------


class ScoreSummaryItem(BaseModel):
    """Aggregated score summary for one metric."""

    metric_name: str
    avg_score: float | None
    min_score: float | None
    max_score: float | None
    median_score: float | None
    success_count: int
    failed_count: int
    latest_score_at: str | None


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
# Schemas -- Session eval runs
# ---------------------------------------------------------------------------


class SessionEvalRunFilters(BaseModel):
    """Filters for session-level evaluation runs."""

    date_from: str | None = Field(default=None, description="ISO 8601 datetime.")
    date_to: str | None = Field(default=None, description="ISO 8601 datetime.")
    user_id: str | None = Field(default=None, description="Exact user ID string.")
    has_error: bool | None = Field(default=None, description="Only sessions with/without errors.")
    tags: list[str] | None = Field(default=None, description="Traces matching ANY of these tags.")
    min_trace_count: int | None = Field(default=None, ge=1, description="Minimum traces in a session.")


class CreateSessionEvalRunRequest(BaseModel):
    """Create a filter-based session eval run."""

    name: str | None = Field(default=None, description="Human-readable label.")
    metrics: list[str] = Field(min_length=1, description="Session metric names (e.g. ['agent_reliability']).")
    filters: SessionEvalRunFilters = Field(default_factory=SessionEvalRunFilters)
    sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="Fraction of sessions to evaluate.")
    model: str | None = Field(default=None, description="LLM model override for judge calls.")
    signal_weights: dict[str, float] | None = Field(default=None, description="Override default signal weights.")


class CreateBatchSessionEvalRunRequest(BaseModel):
    """Create a session eval run for explicit session IDs."""

    session_ids: list[str] = Field(min_length=1, description="List of session ID strings.")
    metrics: list[str] = Field(min_length=1, description="Session metric names.")
    name: str | None = Field(default=None, description="Human-readable label.")
    model: str | None = Field(default=None, description="LLM model override for judge calls.")
    signal_weights: dict[str, float] | None = Field(default=None, description="Override default signal weights.")


class SessionScoreResponse(BaseModel):
    """Full session score representation."""

    id: UUID
    session_id: str
    project_id: UUID
    name: str
    data_type: str
    value: str | None
    source: str
    status: str
    eval_run_id: UUID | None
    author_user_id: str | None
    reason: str | None
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Metric discovery
# ---------------------------------------------------------------------------


@router.get("/providers", response_model=list[ProviderInfo])
async def get_available_providers(
    ctx: ApiContext = Depends(require_project),
) -> list[ProviderInfo]:
    """List LLM providers and their availability.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    from app.infrastructure.llm.engine import LLMEngine

    engine = LLMEngine()
    return [ProviderInfo(**p) for p in engine.available_providers()]


@router.get("/trace-metrics", response_model=list[MetricSummary])
async def get_available_metrics(
    ctx: ApiContext = Depends(require_project),
) -> list[MetricSummary]:
    """List all registered evaluation metrics.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    names = list_metrics()
    return [
        MetricSummary(name=i["name"], description=i["description"], category=i["category"])
        for i in (get_metric_summary(n) for n in names)
    ]


# ---------------------------------------------------------------------------
# Trace eval runs
# ---------------------------------------------------------------------------


@router.get("/trace-runs/template", response_model=EvalRunTemplate)
async def get_eval_run_template(
    metric: str = Query(description="Metric name to build the template for"),
    ctx: ApiContext = Depends(require_project),
) -> EvalRunTemplate:
    """Return a pre-filled eval run template for a single metric.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    from app.infrastructure.llm.engine import LLMEngine
    from app.registry.exceptions import ValidationError

    if metric not in list_metrics():
        raise ValidationError(f"Unknown metric: {metric}")
    info = get_metric_info(metric)
    engine = LLMEngine()
    return EvalRunTemplate(
        metric=_metric_to_info(info),
        filters=EvalRunFilters(),
        sampling_rate=1.0,
        model=engine.default_model,
    )


@router.post("/trace-runs", status_code=202, response_model=EvalRunResponse)
@limiter.limit("50/minute")
async def create_eval_run(
    request: Request,
    body: CreateEvalRunRequest,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunResponse:
    """Create a filtered eval run.

    Resolves traces matching the provided filters, optionally samples
    a fraction of them, then dispatches a background Celery task to
    run the requested metrics asynchronously via an LLM judge.

    **Request body fields:**

    - **name** *(string, optional)*: Human-readable label, e.g. ``"Weekly prod eval"``.
    - **metrics** *(string[], required)*: Metric names to run. Get available names
      from ``GET /evaluations/trace-metrics``. Example: ``["task_completion", "tool_correctness"]``.
    - **filters** *(object, optional)*: Trace selection filters. All fields optional:
        - **date_from**: ISO 8601 datetime, e.g. ``"2025-01-15T00:00:00Z"``.
          Includes traces started on or after this time.
        - **date_to**: ISO 8601 datetime. Includes traces started before this time (exclusive).
        - **status**: One of ``PENDING``, ``RUNNING``, ``COMPLETED``, ``ERROR``.
        - **session_id**: Exact session ID string.
        - **user_id**: Exact user ID string.
        - **tags**: Array of strings, e.g. ``["production", "v2"]``. Matches traces with ANY tag.
        - **name**: Substring match on trace name (case-insensitive).
    - **sampling_rate** *(float, optional, default 1.0)*: Fraction of matching traces
      to evaluate. ``1.0`` = all, ``0.1`` = random 10%.
    - **model** *(string, optional)*: LLM model override, e.g. ``"openai/gpt-4o"``.
      Uses system default if null.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``

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
    )
    return _run_to_detail(run)


@router.post("/trace-runs/batch", status_code=202, response_model=EvalRunResponse)
@limiter.limit("50/minute")
async def create_batch_eval_run(
    request: Request,
    body: CreateBatchEvalRunRequest,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunResponse:
    """Create an eval run for an explicit list of trace IDs.

    Evaluates exactly the provided traces with all requested metrics.
    All metrics for all traces are processed in a single sequential
    Celery task -- no race conditions on concurrent writes.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``

    Rate limit: ``50/min``
    """
    svc = EvalService(session)
    run = await svc.create_batch_eval_run(
        project_id=ctx.project.id,
        trace_ids=body.trace_ids,
        metric_names=body.metrics,
        model=body.model,
        name=body.name,
    )
    return _run_to_detail(run)


@router.get("/trace-runs", response_model=PaginatedResponse[EvalRunResponse])
async def list_eval_runs(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    status: EvaluationStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[EvalRunResponse]:
    """List trace eval runs (summary view).

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    runs, total = await svc.list_eval_runs(
        ctx.project.id, status=status, target_type="TRACE", limit=limit, offset=offset
    )
    return PaginatedResponse(
        items=[_run_to_detail(r) for r in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/trace-runs/{run_id}", response_model=EvalRunResponse)
async def get_eval_run(
    run_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunResponse:
    """Get full eval run detail.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    run = await svc.get_eval_run(run_id, ctx.project.id)
    return _run_to_detail(run)


@router.delete("/trace-runs/{run_id}", status_code=204)
async def delete_eval_run(
    run_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    delete_scores: bool = Query(default=False, description="Also delete all trace scores created by this run."),
) -> None:
    """Delete an eval run.

    By default, only the run record is deleted (scores are preserved
    with ``eval_run_id`` set to NULL via CASCADE). Pass
    ``?delete_scores=true`` to also delete all scores from this run.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    await svc.delete_eval_run(run_id, ctx.project.id, delete_scores=delete_scores)


@router.post("/trace-runs/{run_id}/retry", status_code=202, response_model=EvalRunResponse)
@limiter.limit("50/minute")
async def retry_failed_eval_run(
    request: Request,
    run_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunResponse:
    """Retry failed metrics from a completed eval run.

    Creates a new eval run targeting only the trace+metric pairs that
    failed in the original run. Returns 422 if the original run has
    no failures to retry.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``

    Rate limit: ``50/min``
    """
    svc = EvalService(session)
    run = await svc.retry_failed_run(run_id, ctx.project.id)
    return _run_to_detail(run)


@router.get("/trace-runs/{run_id}/scores", response_model=list[TraceScoreResponse])
async def get_scores_for_run(
    run_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> list[TraceScoreResponse]:
    """List all trace scores produced by a specific eval run.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    scores = await svc.get_scores_for_run(run_id, ctx.project.id)
    return [_score_to_detail(s) for s in scores]


# ---------------------------------------------------------------------------
# Trace scores
# ---------------------------------------------------------------------------


@router.post("/trace-scores", status_code=201, response_model=TraceScoreResponse)
async def create_trace_score(
    body: CreateTraceScoreRequest,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> TraceScoreResponse:
    """Manually create a trace score.

    Use ``source=ANNOTATION`` for human-created scores from the dashboard,
    or ``source=PROGRAMMATIC`` for SDK/API-submitted scores.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    score = await svc.create_score(
        project_id=ctx.project.id,
        trace_id=body.trace_id,
        name=body.name,
        value=body.value,
        data_type=body.data_type,
        source=body.source,
        reason=body.reason,
        metadata=body.metadata,
    )
    return _score_to_detail(score)


@router.get("/trace-scores", response_model=PaginatedResponse[TraceScoreResponse])
async def list_trace_scores(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    trace_id: UUID | None = Query(default=None, description="Filter by trace UUID"),
    metric_name: str | None = Query(default=None, alias="name", description="Filter by metric name (exact match)"),
    source: ScoreSource | None = Query(
        default=None, description="Filter by score source: AUTOMATED, ANNOTATION, PROGRAMMATIC"
    ),
    status: ScoreStatus | None = Query(default=None, description="Filter by score status: SUCCESS, FAILED, PENDING"),
    data_type: ScoreDataType | None = Query(
        default=None, description="Filter by data type: NUMERIC, BOOLEAN, CATEGORICAL"
    ),
    eval_run_id: UUID | None = Query(default=None, description="Filter by eval run UUID"),
    environment: str | None = Query(default=None, description="Filter by trace environment (exact match)"),
    date_from: datetime | None = Query(
        default=None, description="ISO 8601 datetime. Include scores created on or after."
    ),
    date_to: datetime | None = Query(
        default=None, description="ISO 8601 datetime. Include scores created before (exclusive)."
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
) -> PaginatedResponse[TraceScoreResponse]:
    """List trace scores (summary view) with comprehensive filters.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    scores, total = await svc.list_scores(
        ctx.project.id,
        name=metric_name,
        trace_id=trace_id,
        source=source,
        status=status,
        data_type=data_type,
        eval_run_id=eval_run_id,
        environment=environment,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(
        items=[_score_to_detail(s) for s in scores],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/trace-scores/{trace_id}", response_model=list[TraceScoreResponse])
async def get_scores_for_trace(
    trace_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> list[TraceScoreResponse]:
    """Get the latest score per metric for a specific trace.

    Returns one score per metric name, deduplicated by most recent
    ``created_at`` regardless of status. The dashboard uses this to
    display a score overview panel for the trace.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    scores = await svc.get_latest_scores_for_trace(trace_id, ctx.project.id)
    return [_score_to_detail(s) for s in scores]


@router.patch("/trace-scores/{score_id}", response_model=TraceScoreResponse)
async def update_trace_score(
    score_id: UUID,
    body: UpdateTraceScoreRequest,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> TraceScoreResponse:
    """Manually edit a trace score.

    Only ``value``, ``reason``, and ``metadata`` can be changed by the
    caller. ``status`` is automatically set to SUCCESS, ``source`` is
    changed to ANNOTATION, and ``updated_at`` is set to now.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    score = await svc.update_score(
        score_id=score_id,
        project_id=ctx.project.id,
        value=body.value,
        reason=body.reason,
        metadata=body.metadata,
    )
    return _score_to_detail(score)


@router.delete("/trace-scores/{score_id}", status_code=204)
async def delete_trace_score(
    score_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a single trace score.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    await svc.delete_score(score_id, ctx.project.id)


# ---------------------------------------------------------------------------
# Analytics (namespaced under /analytics/trace-scores/ for future
# session-scores parity: /analytics/session-scores/...)
# ---------------------------------------------------------------------------


@router.get("/analytics/trace-scores/summary", response_model=list[ScoreSummaryItem])
async def get_trace_score_analytics_summary(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    date_from: datetime | None = Query(
        default=None, description="ISO 8601 datetime. Include scores created on or after."
    ),
    date_to: datetime | None = Query(
        default=None, description="ISO 8601 datetime. Include scores created before (exclusive)."
    ),
) -> list[ScoreSummaryItem]:
    """Aggregated trace score summary per metric.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    data = await svc.get_score_summary(ctx.project.id, date_from=date_from, date_to=date_to)
    return [ScoreSummaryItem(**d) for d in data]


@router.get("/analytics/trace-scores/trend", response_model=list[ScoreTrendItem])
async def get_trace_score_analytics_trend(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    metric_name: str = Query(..., description="Metric name to get trend for"),
    date_from: datetime | None = Query(default=None, description="ISO 8601 datetime."),
    date_to: datetime | None = Query(default=None, description="ISO 8601 datetime."),
    granularity: AnalyticsGranularity = Query(
        default=AnalyticsGranularity.DAY, description="Time bucket: hour, day, week"
    ),
) -> list[ScoreTrendItem]:
    """Time series of average trace scores by metric.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    data = await svc.get_score_trend(
        ctx.project.id,
        metric_name=metric_name,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
    )
    return [ScoreTrendItem(**d) for d in data]


@router.get("/analytics/trace-scores/distribution", response_model=list[ScoreDistributionItem])
async def get_trace_score_analytics_distribution(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    metric_name: str = Query(..., description="Metric name to get distribution for"),
    date_from: datetime | None = Query(default=None, description="ISO 8601 datetime."),
    date_to: datetime | None = Query(default=None, description="ISO 8601 datetime."),
    buckets: int = Query(default=10, ge=1, le=100, description="Number of histogram buckets (1-100)"),
) -> list[ScoreDistributionItem]:
    """Histogram of trace score values for a metric.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
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


def _build_prompt_preview(preview_dict: dict[str, str]) -> list[PromptPreview]:
    return [PromptPreview(stage=stage, prompt=text) for stage, text in preview_dict.items()]


def _metric_to_info(info: dict[str, Any]) -> MetricInfo:
    return MetricInfo(
        name=info["name"],
        description=info["description"],
        category=info["category"],
        default_threshold=info["default_threshold"],
        prompt_preview=_build_prompt_preview(info["prompt_preview"]),
    )


def _run_to_detail(run) -> EvalRunResponse:
    return EvalRunResponse(
        id=run.id,
        name=run.name,
        status=run.status,
        metric_names=run.metric_names,
        total_traces=run.total_traces,
        evaluated_count=run.evaluated_count,
        failed_count=run.failed_count,
        created_at=run.created_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        project_id=run.project_id,
        target_type=run.target_type,
        filters=run.filters,
        sampling_rate=run.sampling_rate,
        model=run.model,
        monitor_id=run.monitor_id,
        error_message=run.error_message,
    )


def _score_to_detail(score) -> TraceScoreResponse:
    return TraceScoreResponse(
        id=score.id,
        trace_id=score.trace_id,
        name=score.name,
        value=score.value,
        status=score.status,
        source=score.source,
        created_at=score.created_at.isoformat(),
        project_id=score.project_id,
        data_type=score.data_type,
        eval_run_id=score.eval_run_id,
        author_user_id=score.author_user_id,
        reason=score.reason,
        environment=score.environment,
        config_id=score.config_id,
        metadata=score.metadata,
        updated_at=score.updated_at.isoformat(),
    )


def _session_score_to_detail(score) -> SessionScoreResponse:
    return SessionScoreResponse(
        id=score.id,
        session_id=score.session_id,
        project_id=score.project_id,
        name=score.name,
        data_type=score.data_type,
        value=score.value,
        source=score.source,
        status=score.status,
        eval_run_id=score.eval_run_id,
        author_user_id=score.author_user_id,
        reason=score.reason,
        metadata=score.metadata,
        created_at=score.created_at.isoformat(),
        updated_at=score.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Session metric discovery
# ---------------------------------------------------------------------------


@router.get("/session-metrics", response_model=list[MetricSummary])
async def get_available_session_metrics(
    ctx: ApiContext = Depends(require_project),
) -> list[MetricSummary]:
    """List all registered session evaluation metrics.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    names = list_session_metrics()
    return [
        MetricSummary(name=i["name"], description=i["description"], category=i["category"])
        for i in (get_session_metric_summary(n) for n in names)
    ]


# ---------------------------------------------------------------------------
# Session eval runs
# ---------------------------------------------------------------------------


@router.post("/session-runs", status_code=202, response_model=EvalRunResponse)
@limiter.limit("50/minute")
async def create_session_eval_run(
    request: Request,
    body: CreateSessionEvalRunRequest,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunResponse:
    """Create a filter-based session eval run.

    Resolves sessions matching the provided filters, then dispatches a
    background Celery task that computes trace-level signals and
    aggregates them into session-level metrics.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``

    Rate limit: ``50/min``
    """
    svc = EvalService(session)
    filters_dict = body.filters.model_dump(exclude_none=True)
    run = await svc.create_session_eval_run(
        project_id=ctx.project.id,
        metric_names=body.metrics,
        filters=filters_dict,
        sampling_rate=body.sampling_rate,
        model=body.model,
        name=body.name,
        signal_weights=body.signal_weights,
    )
    return _run_to_detail(run)


@router.post("/session-runs/batch", status_code=202, response_model=EvalRunResponse)
@limiter.limit("50/minute")
async def create_batch_session_eval_run(
    request: Request,
    body: CreateBatchSessionEvalRunRequest,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunResponse:
    """Create a session eval run for explicit session IDs.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``

    Rate limit: ``50/min``
    """
    svc = EvalService(session)
    run = await svc.create_batch_session_eval_run(
        project_id=ctx.project.id,
        session_ids=body.session_ids,
        metric_names=body.metrics,
        model=body.model,
        name=body.name,
        signal_weights=body.signal_weights,
    )
    return _run_to_detail(run)


@router.get("/session-runs", response_model=PaginatedResponse[EvalRunResponse])
async def list_session_eval_runs(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    status: EvaluationStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[EvalRunResponse]:
    """List session eval runs.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    runs, total = await svc.list_eval_runs(
        ctx.project.id, status=status, target_type="SESSION", limit=limit, offset=offset
    )
    return PaginatedResponse(
        items=[_run_to_detail(r) for r in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/session-runs/{run_id}", response_model=EvalRunResponse)
async def get_session_eval_run(
    run_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunResponse:
    """Get full session eval run detail.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    run = await svc.get_eval_run(run_id, ctx.project.id)
    return _run_to_detail(run)


@router.delete("/session-runs/{run_id}", status_code=204)
async def delete_session_eval_run(
    run_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    delete_scores: bool = Query(default=False, description="Also delete all session scores from this run."),
) -> None:
    """Delete a session eval run.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    await svc.delete_eval_run(run_id, ctx.project.id, delete_scores=delete_scores)


@router.post("/session-runs/{run_id}/retry", status_code=202, response_model=EvalRunResponse)
@limiter.limit("50/minute")
async def retry_failed_session_eval_run(
    request: Request,
    run_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunResponse:
    """Retry failed metrics from a completed session eval run.

    Creates a new session eval run targeting only the session+metric
    pairs that failed in the original run. Returns 422 if the original
    run has no failures to retry.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``

    Rate limit: ``50/min``
    """
    svc = EvalService(session)
    run = await svc.retry_failed_session_run(run_id, ctx.project.id)
    return _run_to_detail(run)


@router.get("/session-runs/{run_id}/scores", response_model=list[SessionScoreResponse])
async def get_session_scores_for_run(
    run_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> list[SessionScoreResponse]:
    """List all session scores produced by a specific eval run.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    scores = await svc.get_session_scores_for_run(run_id, ctx.project.id)
    return [_session_score_to_detail(s) for s in scores]


# ---------------------------------------------------------------------------
# Session scores
# ---------------------------------------------------------------------------


@router.get("/session-scores", response_model=PaginatedResponse[SessionScoreResponse])
async def list_session_scores(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    session_id: str | None = Query(default=None, description="Filter by session ID"),
    metric_name: str | None = Query(default=None, alias="name", description="Filter by metric name"),
    source: ScoreSource | None = Query(default=None),
    status: ScoreStatus | None = Query(default=None),
    eval_run_id: UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[SessionScoreResponse]:
    """List session scores with filters.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    scores, total = await svc.list_session_scores(
        ctx.project.id,
        name=metric_name,
        session_id=session_id,
        source=source,
        status=status,
        eval_run_id=eval_run_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(
        items=[_session_score_to_detail(s) for s in scores],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/session-scores/{session_id}", response_model=list[SessionScoreResponse])
async def get_scores_for_session(
    session_id: str,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> list[SessionScoreResponse]:
    """Get all scores for a specific session.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    scores = await svc.get_session_scores(session_id, ctx.project.id)
    return [_session_score_to_detail(s) for s in scores]


@router.delete("/session-scores/{score_id}", status_code=204)
async def delete_session_score(
    score_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a single session score.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    await svc.delete_session_score(score_id, ctx.project.id)


# ---------------------------------------------------------------------------
# Session score analytics
# ---------------------------------------------------------------------------


@router.get("/analytics/session-scores/summary", response_model=list[ScoreSummaryItem])
async def get_session_score_analytics_summary(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> list[ScoreSummaryItem]:
    """Aggregated session score summary per metric.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    data = await svc.get_session_score_summary(ctx.project.id, date_from=date_from, date_to=date_to)
    return [ScoreSummaryItem(**d) for d in data]


@router.get("/analytics/session-scores/trend", response_model=list[ScoreTrendItem])
async def get_session_score_analytics_trend(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    metric_name: str = Query(..., description="Metric name to get trend for"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    granularity: AnalyticsGranularity = Query(default=AnalyticsGranularity.DAY),
) -> list[ScoreTrendItem]:
    """Time series of average session scores by metric.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    data = await svc.get_session_score_trend(
        ctx.project.id,
        metric_name=metric_name,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
    )
    return [ScoreTrendItem(**d) for d in data]


@router.get("/analytics/session-scores/distribution", response_model=list[ScoreDistributionItem])
async def get_session_score_analytics_distribution(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    metric_name: str = Query(..., description="Session metric name to get distribution for"),
    date_from: datetime | None = Query(default=None, description="ISO 8601 datetime."),
    date_to: datetime | None = Query(default=None, description="ISO 8601 datetime."),
    buckets: int = Query(default=10, ge=1, le=100, description="Number of histogram buckets (1-100)"),
) -> list[ScoreDistributionItem]:
    """Histogram of session score values for a metric.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    data = await svc.get_session_score_distribution(
        ctx.project.id,
        metric_name,
        date_from=date_from,
        date_to=date_to,
        buckets=buckets,
    )
    return [ScoreDistributionItem(**d) for d in data]


# ---------------------------------------------------------------------------
# Schemas -- Session score history & comparison
# ---------------------------------------------------------------------------


class SessionScoreHistoryItem(BaseModel):
    """A single data point in a session's score evolution over time."""

    metric_name: str
    score: float | None
    eval_run_id: str | None
    created_at: str | None
    status: str


class SessionComparisonItem(BaseModel):
    """A session's latest score for a metric, used in leaderboard/ranking views."""

    session_id: str
    score: float | None
    evaluated_at: str | None
    eval_run_id: str | None


# ---------------------------------------------------------------------------
# Session score history & comparison endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/analytics/session-scores/history/{session_id}",
    response_model=list[SessionScoreHistoryItem],
)
async def get_session_score_history(
    session_id: str,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    metric_name: str | None = Query(default=None, description="Filter to a single metric name."),
    limit: int = Query(default=50, ge=1, le=200, description="Max data points to return."),
) -> list[SessionScoreHistoryItem]:
    """Score evolution for a specific session across re-evaluations over time.

    Returns one row per (metric, eval_run) ordered chronologically, showing
    how the session's scores changed as new traces arrived and the session
    was re-evaluated. Useful for "session health over time" dashboard charts.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    data = await svc.get_session_score_history(ctx.project.id, session_id, metric_name=metric_name, limit=limit)
    return [SessionScoreHistoryItem(**d) for d in data]


@router.get(
    "/analytics/session-scores/comparison",
    response_model=PaginatedResponse[SessionComparisonItem],
)
async def get_session_score_comparison(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    metric_name: str = Query(..., description="Metric name to rank sessions by."),
    sort_order: str = Query(
        default="asc",
        description="Sort order: 'asc' (worst first, good for finding problems) or 'desc' (best first).",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Page size."),
    offset: int = Query(default=0, ge=0, description="Number of items to skip."),
) -> PaginatedResponse[SessionComparisonItem]:
    """Leaderboard: latest score per session for a metric, sorted by value.

    Shows each session's most recent score for the requested metric,
    ranked by value. Use ``sort_order=asc`` to surface the worst-performing
    sessions first (e.g. "Bottom 10 by agent_reliability").

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    items, total = await svc.get_session_score_comparison(
        ctx.project.id, metric_name, sort_order=sort_order, limit=limit, offset=offset
    )
    return PaginatedResponse(
        items=[SessionComparisonItem(**d) for d in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Schemas -- Monitors
# ---------------------------------------------------------------------------


class CreateMonitorRequest(BaseModel):
    """Create an evaluation monitor that spawns runs on a cadence."""

    name: str = Field(description="Human-readable name for the monitor, e.g. 'Daily prod trace eval'.")
    target_type: str = Field(
        description="Evaluation scope: ``'TRACE'`` for trace-level metrics or ``'SESSION'`` for session-level metrics."
    )
    metrics: list[str] = Field(
        min_length=1,
        description=(
            "Metric names to run on each scheduled eval. "
            "For TRACE monitors use ``GET /evaluations/trace-metrics``; "
            "for SESSION monitors use ``GET /evaluations/session-metrics`` to list available names. "
            "Example: ``['task_completion', 'step_efficiency']``."
        ),
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "JSON object defining which traces/sessions the monitor targets. "
            "Pass ``{}`` to match everything in the project. "
            "**TRACE monitors** accept: ``date_from`` (ISO 8601), ``date_to`` (ISO 8601), "
            "``status`` (PENDING|RUNNING|COMPLETED|ERROR), ``session_id``, ``user_id``, "
            "``tags`` (string array, ANY match), ``name`` (substring, case-insensitive). "
            "**SESSION monitors** accept: ``date_from``, ``date_to``, ``user_id``, "
            "``has_error`` (bool), ``tags``, ``min_trace_count`` (int). "
            'Example: ``{"status": "COMPLETED", "tags": ["production"]}``.'
        ),
    )
    sampling_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Fraction of matching traces/sessions to evaluate per run. 1.0 = all, 0.1 = random 10%.",
    )
    model: str | None = Field(
        default=None,
        description="LLM model override for judge calls (e.g. ``'openai/gpt-4o'``). Uses system default if null.",
    )
    cadence: str = Field(
        description=(
            "How often the monitor fires. Predefined intervals: ``'every_6h'``, ``'daily'``, ``'weekly'``. "
            "Custom cron: ``'cron:<5-part expression>'`` where the five parts are "
            "``minute hour day-of-month month day-of-week``. "
            "Examples: ``'cron:0 3 * * *'`` (daily at 3 AM UTC), "
            "``'cron:0 6 * * 1-5'`` (weekdays at 6 AM), "
            "``'cron:0 */4 * * *'`` (every 4 hours)."
        ),
    )
    only_if_changed: bool = Field(
        default=True,
        description=(
            "When true, the scheduled run is skipped if no new traces/sessions "
            "have arrived since the last run, saving LLM costs. "
            "Set to false to always run on schedule regardless of new data."
        ),
    )
    signal_weights: dict[str, float] | None = Field(
        default=None,
        description=(
            "Override default signal weights for session-level aggregation. "
            "**Only valid for SESSION monitors** (rejected for TRACE). "
            "Keys: ``confidence``, ``loop_detection``, ``tool_correctness``, ``coherence``. "
            "Defaults: confidence=1.0, loop_detection=1.0, tool_correctness=0.8, coherence=1.0. "
            'Example: ``{"confidence": 1.0, "loop_detection": 1.5}``.'
        ),
    )


class UpdateMonitorRequest(BaseModel):
    """Partial update of a monitor's configuration."""

    name: str | None = None
    metrics: list[str] | None = None
    filters: dict[str, Any] | None = None
    sampling_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    model: str | None = None
    cadence: str | None = None
    only_if_changed: bool | None = None
    signal_weights: dict[str, float] | None = None


class MonitorResponse(BaseModel):
    """Full evaluation monitor representation."""

    id: UUID
    project_id: UUID
    name: str
    target_type: str
    metric_names: list[str]
    filters: dict[str, Any]
    sampling_rate: float
    model: str | None
    cadence: str
    only_if_changed: bool
    status: str
    last_run_at: str | None
    last_run_id: UUID | None
    next_run_at: str | None
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Monitor endpoints
# ---------------------------------------------------------------------------


@router.post("/monitors", status_code=201, response_model=MonitorResponse)
async def create_monitor(
    body: CreateMonitorRequest,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> MonitorResponse:
    """Create an evaluation monitor that spawns eval runs on a recurring schedule.

    Monitors persist a reusable evaluation configuration (target type, metrics,
    filters, cadence) and the system automatically creates eval runs at each
    scheduled interval.  If ``only_if_changed`` is true (default), runs are
    skipped when no new data has arrived since the previous run.

    **Request body fields:**

    - **name** *(string, required)*: Human-readable label, e.g. ``"Daily prod eval"``.
    - **target_type** *(string, required)*: ``"TRACE"`` or ``"SESSION"``.
    - **metrics** *(string[], required)*: Metric names to run. Use
      ``GET /evaluations/trace-metrics`` (TRACE) or ``GET /evaluations/session-metrics``
      (SESSION) for available names.
    - **filters** *(object, optional, default {})*: Scope the data the monitor evaluates.
      Pass ``{}`` to match everything. Accepted keys depend on ``target_type``:
        - **TRACE**: ``date_from``, ``date_to`` (ISO 8601), ``status``
          (PENDING/RUNNING/COMPLETED/ERROR), ``session_id``, ``user_id``,
          ``tags`` (string[]), ``name`` (substring match).
        - **SESSION**: ``date_from``, ``date_to``, ``user_id``, ``has_error`` (bool),
          ``tags`` (string[]), ``min_trace_count`` (int).
    - **cadence** *(string, required)*: Firing schedule. Predefined: ``"every_6h"``,
      ``"daily"``, ``"weekly"``. Custom cron: ``"cron:<min hour dom month dow>"``,
      e.g. ``"cron:0 3 * * *"`` (daily 3 AM UTC), ``"cron:0 6 * * 1-5"``
      (weekdays 6 AM).
    - **sampling_rate** *(float, optional, default 1.0)*: Fraction of matching
      items to evaluate per run (0.0–1.0).
    - **model** *(string, optional)*: LLM model override, e.g. ``"openai/gpt-4o"``.
    - **only_if_changed** *(bool, optional, default true)*: Skip the run if no
      new traces/sessions exist since the last run.
    - **signal_weights** *(object, optional, SESSION only)*: Override signal
      aggregation weights. Keys: ``confidence``, ``loop_detection``,
      ``tool_correctness``, ``coherence``.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    monitor = await svc.create_monitor(
        project_id=ctx.project.id,
        name=body.name,
        target_type=body.target_type,
        metric_names=body.metrics,
        cadence=body.cadence,
        filters=body.filters,
        sampling_rate=body.sampling_rate,
        model=body.model,
        only_if_changed=body.only_if_changed,
        signal_weights=body.signal_weights,
    )
    return _monitor_to_response(monitor)


@router.get("/monitors", response_model=PaginatedResponse[MonitorResponse])
async def list_monitors(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    status: MonitorStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[MonitorResponse]:
    """List evaluation monitors.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    monitors, total = await svc.list_monitors(ctx.project.id, status=status, limit=limit, offset=offset)
    return PaginatedResponse(
        items=[_monitor_to_response(m) for m in monitors],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/monitors/{monitor_id}", response_model=MonitorResponse)
async def get_monitor(
    monitor_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> MonitorResponse:
    """Get evaluation monitor detail.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    monitor = await svc.get_monitor(monitor_id, ctx.project.id)
    return _monitor_to_response(monitor)


@router.patch("/monitors/{monitor_id}", response_model=MonitorResponse)
async def update_monitor(
    monitor_id: UUID,
    body: UpdateMonitorRequest,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> MonitorResponse:
    """Update an evaluation monitor.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    fields = body.model_dump(exclude_none=True)
    monitor = await svc.update_monitor(monitor_id, ctx.project.id, **fields)
    return _monitor_to_response(monitor)


@router.delete("/monitors/{monitor_id}", status_code=204)
async def delete_monitor(
    monitor_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an evaluation monitor. Spawned runs are preserved.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    await svc.delete_monitor(monitor_id, ctx.project.id)


@router.post("/monitors/{monitor_id}/pause", response_model=MonitorResponse)
async def pause_monitor(
    monitor_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> MonitorResponse:
    """Pause an evaluation monitor. Idempotent if already paused.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    monitor = await svc.pause_monitor(monitor_id, ctx.project.id)
    return _monitor_to_response(monitor)


@router.post("/monitors/{monitor_id}/resume", response_model=MonitorResponse)
async def resume_monitor(
    monitor_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> MonitorResponse:
    """Resume a paused evaluation monitor. Idempotent if already active.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    monitor = await svc.resume_monitor(monitor_id, ctx.project.id)
    return _monitor_to_response(monitor)


@router.post("/monitors/{monitor_id}/trigger", status_code=202, response_model=EvalRunResponse)
@limiter.limit("10/minute")
async def trigger_monitor(
    request: Request,
    monitor_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunResponse:
    """Force an immediate eval run from a monitor, ignoring cadence.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``

    Rate limit: ``10/min``
    """
    svc = EvalService(session)
    run = await svc.trigger_monitor(monitor_id, ctx.project.id)
    return _run_to_detail(run)


@router.get("/monitors/{monitor_id}/runs", response_model=PaginatedResponse[EvalRunResponse])
async def list_monitor_runs(
    monitor_id: UUID,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[EvalRunResponse]:
    """List eval runs spawned by a specific monitor.

    Auth: ``Bearer`` + ``X-Project-ID`` | ``X-API-Key`` + ``X-Project-Name``
    """
    svc = EvalService(session)
    runs, total = await svc.list_monitor_runs(monitor_id, ctx.project.id, limit=limit, offset=offset)
    return PaginatedResponse(
        items=[_run_to_detail(r) for r in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


def _monitor_to_response(m) -> MonitorResponse:
    return MonitorResponse(
        id=m.id,
        project_id=m.project_id,
        name=m.name,
        target_type=m.target_type,
        metric_names=m.metric_names,
        filters=m.filters,
        sampling_rate=m.sampling_rate,
        model=m.model,
        cadence=m.cadence,
        only_if_changed=m.only_if_changed,
        status=m.status,
        last_run_at=m.last_run_at.isoformat() if m.last_run_at else None,
        last_run_id=m.last_run_id,
        next_run_at=m.next_run_at.isoformat() if m.next_run_at else None,
        created_at=m.created_at.isoformat(),
        updated_at=m.updated_at.isoformat(),
    )

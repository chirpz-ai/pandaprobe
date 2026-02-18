"""Routes for triggering and querying evaluations.

Evaluations run **asynchronously**: the POST endpoint creates the job
and returns ``202 Accepted``.  A background Celery worker executes
the metrics and persists the results.  Use the GET endpoints to poll
for completion or retrieve scores.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import APIKeyContext, require_api_key
from app.core.evals.metrics import list_metrics
from app.infrastructure.db.engine import get_db_session
from app.registry.constants import EvaluationStatus
from app.services.eval_service import EvalService

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateEvaluationRequest(BaseModel):
    """Payload for triggering an evaluation."""

    trace_id: UUID
    metrics: list[str] = Field(min_length=1, description="List of metric names to run")


class EvaluationResultResponse(BaseModel):
    """Single metric result inside an evaluation."""

    id: UUID
    metric_name: str
    score: float
    threshold: float
    success: bool
    reason: str | None
    metadata: dict[str, Any]
    evaluated_at: str


class EvaluationResponse(BaseModel):
    """Full evaluation with results."""

    id: UUID
    trace_id: UUID
    project_id: UUID
    metric_names: list[str]
    status: EvaluationStatus
    results: list[EvaluationResultResponse]
    created_at: str
    completed_at: str | None


class EvaluationAccepted(BaseModel):
    """Returned when an evaluation job is successfully enqueued."""

    id: UUID
    trace_id: UUID
    status: EvaluationStatus
    metrics: list[str]


class MetricListResponse(BaseModel):
    """Available metrics that can be requested."""

    metrics: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/metrics", response_model=MetricListResponse)
async def get_available_metrics() -> MetricListResponse:
    """List all registered evaluation metrics."""
    return MetricListResponse(metrics=list_metrics())


class ProviderInfo(BaseModel):
    """Availability info for a single LLM provider."""

    key: str
    name: str
    description: str
    available: bool
    message: str


@router.get("/providers", response_model=list[ProviderInfo])
async def get_available_providers() -> list[ProviderInfo]:
    """List LLM providers and their availability based on configured credentials."""
    from app.infrastructure.llm.engine import LLMEngine

    engine = LLMEngine()
    return [ProviderInfo(**p) for p in engine.available_providers()]


@router.post("", status_code=202, response_model=EvaluationAccepted)
async def create_evaluation(
    body: CreateEvaluationRequest,
    ctx: APIKeyContext = Depends(require_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationAccepted:
    """Trigger an asynchronous evaluation of a trace.

    The project is resolved automatically from the API key.
    """
    svc = EvalService(session)
    evaluation = await svc.create_evaluation(
        trace_id=body.trace_id,
        project_id=ctx.project_id,
        metric_names=body.metrics,
    )
    return EvaluationAccepted(
        id=evaluation.id,
        trace_id=evaluation.trace_id,
        status=evaluation.status,
        metrics=evaluation.metric_names,
    )


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: UUID,
    ctx: APIKeyContext = Depends(require_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationResponse:
    """Retrieve an evaluation with all its metric results."""
    svc = EvalService(session)
    evaluation = await svc.get_evaluation(evaluation_id, ctx.project_id)
    return _to_response(evaluation)


@router.get("", response_model=list[EvaluationResponse])
async def list_evaluations(
    ctx: APIKeyContext = Depends(require_api_key),
    session: AsyncSession = Depends(get_db_session),
    trace_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[EvaluationResponse]:
    """List evaluations for the project associated with the API key."""
    svc = EvalService(session)
    evaluations = await svc.list_evaluations(ctx.project_id, trace_id=trace_id, limit=limit, offset=offset)
    return [_to_response(e) for e in evaluations]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(evaluation):
    """Map a domain Evaluation to an EvaluationResponse."""
    return EvaluationResponse(
        id=evaluation.id,
        trace_id=evaluation.trace_id,
        project_id=evaluation.project_id,
        metric_names=evaluation.metric_names,
        status=evaluation.status,
        results=[
            EvaluationResultResponse(
                id=r.id,
                metric_name=r.metric_name,
                score=r.score,
                threshold=r.threshold,
                success=r.success,
                reason=r.reason,
                metadata=r.metadata,
                evaluated_at=r.evaluated_at.isoformat(),
            )
            for r in evaluation.results
        ],
        created_at=evaluation.created_at.isoformat(),
        completed_at=evaluation.completed_at.isoformat() if evaluation.completed_at else None,
    )

"""Orchestration logic for the Evaluation domain.

Coordinates creating evaluation jobs, dispatching them to the Celery
worker, and reading results back from the database.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evals.entities import Evaluation
from app.core.evals.metrics import get_metric, list_metrics
from app.infrastructure.db.repositories.eval_repo import EvalRepository
from app.logging import logger
from app.registry.constants import EvaluationStatus
from app.registry.exceptions import NotFoundError, ValidationError


class EvalService:
    """Application service for evaluations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._repo = EvalRepository(session)

    async def create_evaluation(
        self,
        trace_id: UUID,
        org_id: UUID,
        metric_names: list[str],
    ) -> Evaluation:
        """Validate the requested metrics, persist the job, and enqueue it.

        Returns:
            The created Evaluation entity (status=PENDING).

        Raises:
            ValidationError: If any metric name is unrecognised.
        """
        # Validate all metric names before creating the job.
        available = set(list_metrics())
        unknown = set(metric_names) - available
        if unknown:
            raise ValidationError(
                f"Unknown metric(s): {', '.join(sorted(unknown))}. "
                f"Available: {', '.join(sorted(available))}"
            )

        evaluation = Evaluation(
            id=uuid4(),
            trace_id=trace_id,
            org_id=org_id,
            metric_names=metric_names,
            status=EvaluationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        await self._repo.create_evaluation(evaluation)

        # Enqueue background execution.
        from app.infrastructure.queue.tasks import run_evaluation

        run_evaluation.delay(str(evaluation.id), str(org_id))
        logger.info(
            "evaluation_enqueued",
            evaluation_id=str(evaluation.id),
            trace_id=str(trace_id),
            metrics=metric_names,
        )

        return evaluation

    async def get_evaluation(self, evaluation_id: UUID, org_id: UUID) -> Evaluation:
        """Fetch an evaluation or raise ``NotFoundError``."""
        evaluation = await self._repo.get_evaluation(evaluation_id, org_id)
        if evaluation is None:
            raise NotFoundError(f"Evaluation {evaluation_id} not found.")
        return evaluation

    async def list_evaluations(
        self,
        org_id: UUID,
        trace_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Evaluation]:
        """Return paginated evaluations for an organisation."""
        return await self._repo.list_evaluations(
            org_id, trace_id=trace_id, limit=limit, offset=offset
        )

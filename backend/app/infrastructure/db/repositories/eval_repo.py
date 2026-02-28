"""PostgreSQL implementation of the Evaluation repository."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.evals.entities import Evaluation, EvaluationResult
from app.infrastructure.db.models import EvaluationModel, EvaluationResultModel
from app.registry.constants import EvaluationStatus


class EvalRepository:
    """Concrete eval repository backed by PostgreSQL + SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    async def create_evaluation(self, evaluation: Evaluation) -> Evaluation:
        """Insert a new evaluation job row."""
        row = EvaluationModel(
            id=evaluation.id,
            trace_id=evaluation.trace_id,
            project_id=evaluation.project_id,
            metric_names=evaluation.metric_names,
            status=evaluation.status.value,
        )
        self._session.add(row)
        await self._session.flush()
        return evaluation

    async def get_evaluation(self, evaluation_id: UUID, project_id: UUID) -> Evaluation | None:
        """Fetch an evaluation with all its results."""
        stmt = (
            select(EvaluationModel)
            .options(selectinload(EvaluationModel.results))
            .where(EvaluationModel.id == evaluation_id, EvaluationModel.project_id == project_id)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_evaluation(row) if row else None

    async def update_status(self, evaluation_id: UUID, status: EvaluationStatus) -> None:
        """Transition the evaluation to a new status."""
        values: dict = {"status": status.value}
        if status in {EvaluationStatus.COMPLETED, EvaluationStatus.FAILED}:
            values["completed_at"] = datetime.now(timezone.utc)
        stmt = update(EvaluationModel).where(EvaluationModel.id == evaluation_id).values(**values)
        await self._session.execute(stmt)

    async def add_result(self, result: EvaluationResult) -> EvaluationResult:
        """Append a single metric result to an evaluation."""
        row = EvaluationResultModel(
            id=result.id,
            evaluation_id=result.evaluation_id,
            metric_name=result.metric_name,
            score=result.score,
            threshold=result.threshold,
            success=result.success,
            reason=result.reason,
            metadata_=result.metadata,
            evaluated_at=result.evaluated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return result

    async def list_evaluations(
        self,
        project_id: UUID,
        trace_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Evaluation]:
        """List evaluations, optionally filtered by trace."""
        stmt = (
            select(EvaluationModel)
            .options(selectinload(EvaluationModel.results))
            .where(EvaluationModel.project_id == project_id)
        )
        if trace_id is not None:
            stmt = stmt.where(EvaluationModel.trace_id == trace_id)
        stmt = stmt.order_by(EvaluationModel.created_at.desc()).offset(offset).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_evaluation(r) for r in rows]

    # -- Mappers --------------------------------------------------------------

    @staticmethod
    def _to_result(row: EvaluationResultModel) -> EvaluationResult:
        return EvaluationResult(
            id=row.id,
            evaluation_id=row.evaluation_id,
            metric_name=row.metric_name,
            score=row.score,
            threshold=row.threshold,
            success=row.success,
            reason=row.reason,
            metadata=row.metadata_,
            evaluated_at=row.evaluated_at,
        )

    @classmethod
    def _to_evaluation(cls, row: EvaluationModel) -> Evaluation:
        results = [cls._to_result(r) for r in row.results] if row.results else []
        return Evaluation(
            id=row.id,
            trace_id=row.trace_id,
            project_id=row.project_id,
            metric_names=list(row.metric_names),
            status=EvaluationStatus(row.status),
            results=results,
            created_at=row.created_at,
            completed_at=row.completed_at,
        )

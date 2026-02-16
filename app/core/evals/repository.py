"""Abstract repository interface for the Evaluation domain."""

from typing import Protocol
from uuid import UUID

from app.core.evals.entities import Evaluation, EvaluationResult
from app.registry.constants import EvaluationStatus


class AbstractEvalRepository(Protocol):
    """Port that any evaluation persistence adapter must implement."""

    async def create_evaluation(self, evaluation: Evaluation) -> Evaluation:
        """Persist a new evaluation job."""
        ...

    async def get_evaluation(self, evaluation_id: UUID, org_id: UUID) -> Evaluation | None:
        """Fetch an evaluation with all its results."""
        ...

    async def update_status(self, evaluation_id: UUID, status: EvaluationStatus) -> None:
        """Transition the evaluation to a new status."""
        ...

    async def add_result(self, result: EvaluationResult) -> EvaluationResult:
        """Append a single metric result to an evaluation."""
        ...

    async def complete_evaluation(self, evaluation_id: UUID) -> None:
        """Mark the evaluation as COMPLETED with a timestamp."""
        ...

    async def list_evaluations(
        self,
        org_id: UUID,
        trace_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Evaluation]:
        """List evaluations, optionally filtered by trace."""
        ...

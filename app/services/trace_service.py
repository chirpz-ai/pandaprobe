"""Orchestration logic for trace ingestion and retrieval.

The ingestion path serialises the payload and enqueues it to Redis
via Celery so the API can return 202 immediately.  Read operations
go directly to the database through the repository.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.traces.entities import Trace
from app.infrastructure.db.repositories.trace_repo import TraceRepository
from app.logging import logger
from app.registry.exceptions import NotFoundError


class TraceService:
    """Application service for traces."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._repo = TraceRepository(session)

    # -- Write (async via Celery) ---------------------------------------------

    @staticmethod
    def enqueue_trace(trace: Trace) -> str:
        """Push a validated trace payload onto the Celery task queue.

        Returns the Celery task id so the caller can optionally poll
        for completion.
        """
        from app.infrastructure.queue.tasks import process_trace

        payload = trace.model_dump(mode="json")
        result = process_trace.delay(payload)
        logger.info("trace_enqueued", trace_id=str(trace.trace_id), task_id=result.id)
        return result.id

    # -- Read -----------------------------------------------------------------

    async def get_trace(self, trace_id: UUID, project_id: UUID) -> Trace:
        """Fetch a single trace or raise ``NotFoundError``."""
        trace = await self._repo.get_trace(trace_id, project_id)
        if trace is None:
            raise NotFoundError(f"Trace {trace_id} not found.")
        return trace

    async def list_traces(
        self,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Trace]:
        """Return paginated traces for a project."""
        return await self._repo.list_traces(project_id, limit=limit, offset=offset)

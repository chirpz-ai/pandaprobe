"""Orchestration logic for trace ingestion and retrieval.

The ingestion path serialises the payload and enqueues it to Redis
via Celery so the API can return 202 immediately.  Read operations
go directly to the database through the repository.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.traces.entities import Span, Trace
from app.infrastructure.db.repositories.trace_repo import TraceRepository
from app.logging import logger
from app.registry.constants import (
    AnalyticsGranularity,
    SessionSortBy,
    SortOrder,
    TraceSortBy,
    TraceStatus,
)
from app.registry.exceptions import NotFoundError


class TraceService:
    """Application service for traces."""

    def __init__(self, session: AsyncSession) -> None:
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

    # -- Update ----------------------------------------------------------

    async def update_trace(
        self,
        trace_id: UUID,
        project_id: UUID,
        **fields: Any,
    ) -> Trace:
        """Update trace fields or raise ``NotFoundError``."""
        row = await self._repo.update_trace(trace_id, project_id, **fields)
        if row is None:
            raise NotFoundError(f"Trace {trace_id} not found.")
        return self._repo._to_trace(row)

    async def update_span(
        self,
        span_id: UUID,
        trace_id: UUID,
        project_id: UUID,
        **fields: Any,
    ) -> Any:
        """Update span fields or raise ``NotFoundError``."""
        row = await self._repo.update_span(span_id, trace_id, project_id, **fields)
        if row is None:
            raise NotFoundError(f"Span {span_id} not found on trace {trace_id}.")
        return self._repo._to_span(row)

    async def add_spans(
        self,
        trace_id: UUID,
        project_id: UUID,
        spans: list[Span],
    ) -> None:
        """Add spans to an existing trace, or raise ``NotFoundError``."""
        ok = await self._repo.add_spans(trace_id, project_id, spans)
        if not ok:
            raise NotFoundError(f"Trace {trace_id} not found.")

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
        *,
        session_id: str | None = None,
        status: TraceStatus | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        name: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        sort_by: TraceSortBy = TraceSortBy.STARTED_AT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> tuple[list[Row[Any]], int]:
        """Return paginated traces with computed stats and total count."""
        return await self._repo.list_traces(
            project_id,
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

    # -- Delete ----------------------------------------------------------

    async def delete_trace(self, trace_id: UUID, project_id: UUID) -> None:
        """Delete a trace or raise ``NotFoundError``."""
        deleted = await self._repo.delete_trace(trace_id, project_id)
        if not deleted:
            raise NotFoundError(f"Trace {trace_id} not found.")

    # -- Batch -----------------------------------------------------------

    async def batch_delete_traces(
        self,
        project_id: UUID,
        trace_ids: list[UUID],
    ) -> int:
        """Delete multiple traces at once.  Returns count removed."""
        return await self._repo.batch_delete_traces(project_id, trace_ids)

    async def batch_update_tags(
        self,
        project_id: UUID,
        trace_ids: list[UUID],
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
    ) -> int:
        """Add/remove tags on multiple traces.  Returns count affected."""
        return await self._repo.batch_update_tags(
            project_id,
            trace_ids,
            add_tags=add_tags,
            remove_tags=remove_tags,
        )

    # -- Sessions -------------------------------------------------------------

    async def list_sessions(
        self,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
        *,
        user_id: str | None = None,
        has_error: bool | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        tags: list[str] | None = None,
        query: str | None = None,
        sort_by: SessionSortBy = SessionSortBy.RECENT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> tuple[list[Row[Any]], int]:
        """Return paginated session summaries with total count."""
        return await self._repo.list_sessions(
            project_id,
            limit=limit,
            offset=offset,
            user_id=user_id,
            has_error=has_error,
            started_after=started_after,
            started_before=started_before,
            tags=tags,
            query=query,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def get_session_summary(
        self,
        project_id: UUID,
        session_id: str,
    ) -> Row[Any]:
        """Return an aggregated session summary, or raise ``NotFoundError``."""
        row = await self._repo.get_session_summary(project_id, session_id)
        if row is None:
            raise NotFoundError(f"Session '{session_id}' not found.")
        return row

    async def list_session_traces_with_stats(
        self,
        project_id: UUID,
        session_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[Row[Any]], int]:
        """Return paginated session traces with span stats, or raise ``NotFoundError``."""
        rows, total = await self._repo.list_session_traces_with_stats(
            project_id,
            session_id,
            limit=limit,
            offset=offset,
        )
        if total == 0:
            raise NotFoundError(f"No traces found for session '{session_id}'.")
        return rows, total

    async def delete_session(self, project_id: UUID, session_id: str) -> int:
        """Delete all traces in a session.  Raises ``NotFoundError`` if none found."""
        count = await self._repo.delete_session(project_id, session_id)
        if count == 0:
            raise NotFoundError(f"Session '{session_id}' not found.")
        return count

    async def get_session_analytics(
        self,
        project_id: UUID,
        granularity: AnalyticsGranularity,
        started_after: datetime,
        started_before: datetime,
    ) -> list[Row[Any]]:
        """Return time-bucketed session statistics."""
        return await self._repo.get_session_analytics(
            project_id,
            granularity,
            started_after,
            started_before,
        )

    # -- Analytics -------------------------------------------------------

    async def get_trace_analytics(
        self,
        project_id: UUID,
        granularity: AnalyticsGranularity,
        started_after: datetime,
        started_before: datetime,
    ) -> list[Row[Any]]:
        """Return time-bucketed trace statistics (volume, errors, latency)."""
        return await self._repo.get_trace_analytics(
            project_id,
            granularity,
            started_after,
            started_before,
        )

    async def get_token_cost_analytics(
        self,
        project_id: UUID,
        granularity: AnalyticsGranularity,
        started_after: datetime,
        started_before: datetime,
    ) -> list[Row[Any]]:
        """Return time-bucketed token usage and cost from spans."""
        return await self._repo.get_token_cost_analytics(
            project_id,
            granularity,
            started_after,
            started_before,
        )

    async def get_top_models(
        self,
        project_id: UUID,
        started_after: datetime,
        started_before: datetime,
        limit: int = 10,
    ) -> list[Row[Any]]:
        """Return the most-used LLM models within a time window."""
        return await self._repo.get_top_models(
            project_id,
            started_after,
            started_before,
            limit=limit,
        )

    # -- User aggregation ------------------------------------------------

    async def list_trace_users(
        self,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Row[Any]], int]:
        """Return user-level trace aggregation with total count."""
        return await self._repo.list_trace_users(project_id, limit=limit, offset=offset)

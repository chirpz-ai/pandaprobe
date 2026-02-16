"""Celery task definitions for background processing.

Each task runs inside the worker process.  Because Celery workers are
synchronous by default, we use ``asyncio.run()`` to bridge into the
async SQLAlchemy session.
"""

import asyncio
from typing import Any

from app.infrastructure.queue.celery_app import celery
from app.logging import logger


@celery.task(name="process_trace", bind=True, max_retries=3, default_retry_delay=5)
def process_trace(self: Any, payload: dict[str, Any]) -> dict[str, str]:
    """Deserialise a trace payload and persist it to PostgreSQL.

    This task is enqueued by ``TraceService.enqueue_trace()`` and
    executed by the Celery worker.

    Args:
        self: Celery task instance (injected by ``bind=True``).
        payload: JSON-serialisable dict produced by ``Trace.model_dump(mode='json')``.

    Returns:
        A dict with ``trace_id`` and ``status`` for result inspection.
    """
    try:
        return asyncio.run(_persist_trace(payload))
    except Exception as exc:
        logger.error("process_trace_failed", error=str(exc), trace_id=payload.get("trace_id"))
        raise self.retry(exc=exc)


async def _persist_trace(payload: dict[str, Any]) -> dict[str, str]:
    """Async helper that opens a DB session and saves the trace."""
    from app.core.traces.entities import Trace
    from app.infrastructure.db.engine import async_session_factory
    from app.infrastructure.db.repositories.trace_repo import TraceRepository

    trace = Trace.model_validate(payload)

    async with async_session_factory() as session:
        repo = TraceRepository(session)
        await repo.create_trace(trace)
        await session.commit()

    logger.info("trace_persisted", trace_id=str(trace.trace_id))
    return {"trace_id": str(trace.trace_id), "status": "persisted"}

"""Celery task definitions for background processing.

Each task runs inside the worker process.  Because Celery workers are
synchronous by default, we use ``asyncio.run()`` to bridge into the
async SQLAlchemy session.

Two task families:
- **process_trace** -- persist an ingested trace to PostgreSQL.
- **execute_eval_run** -- run metrics against a batch of traces and
  persist trace scores.

**Why NullPool?**  Each ``asyncio.run()`` call creates a new event loop.
A pooled engine holds connections bound to the previous loop, causing
``"attached to a different loop"`` errors on the next task.  ``NullPool``
creates a fresh connection per session and discards it immediately,
avoiding cross-loop contamination.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.queue.celery_app import celery
from app.logging import logger
from app.registry.settings import settings

_worker_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
_worker_session_factory = async_sessionmaker(
    bind=_worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def _worker_session() -> AsyncGenerator:
    """Yield an async session safe for Celery workers.

    Uses a module-level ``NullPool`` engine — safe across event loops
    because NullPool holds zero idle connections.  Each session opens
    a fresh TCP connection and closes it on exit.
    """
    async with _worker_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Trace persistence
# ---------------------------------------------------------------------------


@celery.task(name="process_trace", bind=True, max_retries=3, default_retry_delay=5)
def process_trace(self: Any, payload: dict[str, Any]) -> dict[str, str]:
    """Deserialise a trace payload and persist it to PostgreSQL.

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
    from app.infrastructure.db.repositories.trace_repo import TraceRepository

    trace = Trace.model_validate(payload)

    async with _worker_session() as session:
        repo = TraceRepository(session)
        await repo.upsert_trace(trace)
        await session.commit()

    logger.info("trace_persisted", trace_id=str(trace.trace_id))
    return {"trace_id": str(trace.trace_id), "status": "persisted"}


# ---------------------------------------------------------------------------
# Eval run execution
# ---------------------------------------------------------------------------


@celery.task(name="execute_eval_run", bind=True, max_retries=2, default_retry_delay=10)
def execute_eval_run(
    self: Any,
    run_id: str,
    project_id: str,
    trace_ids: list[str],
    trace_metric_map: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """Run requested metrics against a batch of traces.

    The eval run row must already exist in the database (created by
    the API handler).  This task transitions it through
    PENDING -> RUNNING -> COMPLETED/FAILED.

    Args:
        self: Celery task instance.
        run_id: UUID of the eval run.
        project_id: UUID of the owning project.
        trace_ids: List of trace UUID strings to evaluate.
        trace_metric_map: Optional per-trace metric override. When set,
            each trace only runs the metrics listed for it instead of
            all metrics from the run. Used by retry to avoid Cartesian
            product re-evaluation.

    Returns:
        A dict summarising the eval run outcome.
    """
    try:
        return asyncio.run(_run_eval_run(run_id, project_id, trace_ids, trace_metric_map))
    except Exception as exc:
        logger.error("execute_eval_run_failed", error=str(exc), run_id=run_id)
        asyncio.run(_fail_eval_run(run_id, str(exc)))
        raise self.retry(exc=exc)


async def _run_eval_run(
    run_id: str,
    project_id: str,
    trace_ids: list[str],
    trace_metric_map: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """Core async logic for executing an eval run."""
    from datetime import datetime, timezone
    from uuid import UUID, uuid4

    from app.core.evals.entities import TraceScore
    from app.core.evals.metrics import get_metric
    from app.core.evals.metrics.base import MetricResult
    from app.infrastructure.db.repositories.eval_repo import EvalRepository
    from app.infrastructure.db.repositories.trace_repo import TraceRepository
    from app.infrastructure.llm.engine import LLMEngine
    from app.registry.constants import EvaluationStatus, ScoreDataType, ScoreSource, ScoreStatus

    run_uuid = UUID(run_id)
    proj_uuid = UUID(project_id)

    llm = LLMEngine()

    async with _worker_session() as session:
        eval_repo = EvalRepository(session)
        trace_repo = TraceRepository(session)

        await eval_repo.delete_scores_for_run(run_uuid, proj_uuid)
        await eval_repo.reset_run_counters(run_uuid)
        await eval_repo.update_run_status(run_uuid, EvaluationStatus.RUNNING)
        await session.commit()

        run = await eval_repo.get_eval_run(run_uuid, proj_uuid)
        if run is None:
            raise ValueError(f"Eval run {run_id} not found")

        for tid_str in trace_ids:
            tid = UUID(tid_str)
            trace = await trace_repo.get_trace(tid, proj_uuid)
            if trace is None:
                logger.warning("eval_run_trace_not_found", run_id=run_id, trace_id=tid_str)
                await eval_repo.increment_progress(run_uuid)
                await session.commit()
                continue

            metrics_for_trace = trace_metric_map.get(tid_str, run.metric_names) if trace_metric_map else run.metric_names
            for metric_name in metrics_for_trace:
                metric_cls = get_metric(metric_name)
                metric = metric_cls()

                now = datetime.now(timezone.utc)
                try:
                    result: MetricResult = await metric.evaluate(trace, llm, model=run.model)

                    score = TraceScore(
                        id=uuid4(),
                        trace_id=tid,
                        project_id=proj_uuid,
                        name=metric_name,
                        data_type=ScoreDataType.NUMERIC,
                        value=str(round(result.score, 4)),
                        source=ScoreSource.AUTOMATED,
                        status=ScoreStatus.SUCCESS,
                        eval_run_id=run_uuid,
                        reason=result.reason,
                        environment=trace.environment,
                        metadata=result.metadata,
                        created_at=now,
                        updated_at=now,
                    )
                    await eval_repo.create_score(score)

                    logger.info(
                        "metric_completed",
                        run_id=run_id,
                        trace_id=tid_str,
                        metric=metric_name,
                        score=result.score,
                    )
                except Exception as exc:
                    logger.error(
                        "metric_failed",
                        run_id=run_id,
                        trace_id=tid_str,
                        metric=metric_name,
                        error=str(exc),
                    )
                    failed_score = TraceScore(
                        id=uuid4(),
                        trace_id=tid,
                        project_id=proj_uuid,
                        name=metric_name,
                        data_type=ScoreDataType.NUMERIC,
                        value=None,
                        source=ScoreSource.AUTOMATED,
                        status=ScoreStatus.FAILED,
                        eval_run_id=run_uuid,
                        reason=f"Metric execution failed: {exc}",
                        environment=trace.environment,
                        metadata={},
                        created_at=now,
                        updated_at=now,
                    )
                    await eval_repo.create_score(failed_score)
                    await eval_repo.increment_failed(run_uuid)

            await eval_repo.increment_progress(run_uuid)
            await session.commit()

        await eval_repo.update_run_status(run_uuid, EvaluationStatus.COMPLETED)
        await session.commit()

    logger.info("eval_run_completed", run_id=run_id)
    return {"run_id": run_id, "status": "completed"}


async def _fail_eval_run(run_id: str, error_message: str) -> None:
    """Mark an eval run as FAILED on unrecoverable errors."""
    from uuid import UUID

    from app.infrastructure.db.repositories.eval_repo import EvalRepository
    from app.registry.constants import EvaluationStatus

    try:
        async with _worker_session() as session:
            repo = EvalRepository(session)
            await repo.update_run_status(UUID(run_id), EvaluationStatus.FAILED, error_message=error_message)
            await session.commit()
    except Exception:
        logger.error("fail_eval_run_update_failed", run_id=run_id)

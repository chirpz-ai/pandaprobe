"""Celery task definitions for background processing.

Each task runs inside the worker process.  Because Celery workers are
synchronous by default, we use ``asyncio.run()`` to bridge into the
async SQLAlchemy session.

Two task families:
- **process_trace** -- persist an ingested trace to PostgreSQL.
- **run_evaluation** -- execute metrics against a stored trace using
  an LLM judge and persist the results.
"""

import asyncio
from typing import Any

from app.infrastructure.queue.celery_app import celery
from app.logging import logger


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
    from app.infrastructure.db.engine import async_session_factory
    from app.infrastructure.db.repositories.trace_repo import TraceRepository

    trace = Trace.model_validate(payload)

    async with async_session_factory() as session:
        repo = TraceRepository(session)
        await repo.upsert_trace(trace)
        await session.commit()

    logger.info("trace_persisted", trace_id=str(trace.trace_id))
    return {"trace_id": str(trace.trace_id), "status": "persisted"}


# ---------------------------------------------------------------------------
# Evaluation execution
# ---------------------------------------------------------------------------


@celery.task(name="run_evaluation", bind=True, max_retries=2, default_retry_delay=10)
def run_evaluation(self: Any, evaluation_id: str, project_id: str) -> dict[str, str]:
    """Load a stored trace and run the requested metrics against it.

    The evaluation row must already exist in the database (created by
    the API handler).  This task transitions it through
    PENDING -> RUNNING -> COMPLETED/FAILED.

    Args:
        self: Celery task instance.
        evaluation_id: UUID of the evaluation job.
        project_id: UUID of the owning project.

    Returns:
        A dict summarising the evaluation outcome.
    """
    try:
        return asyncio.run(_execute_evaluation(evaluation_id, project_id))
    except Exception as exc:
        logger.error("run_evaluation_failed", error=str(exc), evaluation_id=evaluation_id)
        asyncio.run(_fail_evaluation(evaluation_id))
        raise self.retry(exc=exc)


async def _execute_evaluation(evaluation_id: str, project_id: str) -> dict[str, str]:
    """Core async logic for running an evaluation job."""
    from datetime import datetime, timezone
    from uuid import UUID, uuid4

    from app.core.evals.entities import EvaluationResult
    from app.core.evals.metrics import get_metric
    from app.core.evals.metrics.base import MetricResult
    from app.infrastructure.db.engine import async_session_factory
    from app.infrastructure.db.repositories.eval_repo import EvalRepository
    from app.infrastructure.db.repositories.trace_repo import TraceRepository
    from app.infrastructure.llm.engine import LLMEngine
    from app.registry.constants import EvaluationStatus

    eval_uuid = UUID(evaluation_id)
    proj_uuid = UUID(project_id)

    llm = LLMEngine()

    async with async_session_factory() as session:
        eval_repo = EvalRepository(session)
        trace_repo = TraceRepository(session)

        # Mark as RUNNING.
        await eval_repo.update_status(eval_uuid, EvaluationStatus.RUNNING)
        await session.commit()

        # Load the evaluation and its target trace.
        evaluation = await eval_repo.get_evaluation(eval_uuid, proj_uuid)
        if evaluation is None:
            raise ValueError(f"Evaluation {evaluation_id} not found")

        trace = await trace_repo.get_trace(evaluation.trace_id, proj_uuid)
        if trace is None:
            raise ValueError(f"Trace {evaluation.trace_id} not found for evaluation")

        # Run each requested metric.
        for metric_name in evaluation.metric_names:
            metric_cls = get_metric(metric_name)
            metric = metric_cls()

            try:
                result: MetricResult = await metric.evaluate(trace, llm)

                eval_result = EvaluationResult(
                    id=uuid4(),
                    evaluation_id=eval_uuid,
                    metric_name=metric_name,
                    score=result.score,
                    threshold=metric.threshold,
                    success=result.score >= metric.threshold,
                    reason=result.reason,
                    metadata=result.metadata,
                    evaluated_at=datetime.now(timezone.utc),
                )
                await eval_repo.add_result(eval_result)
                logger.info(
                    "metric_completed",
                    evaluation_id=evaluation_id,
                    metric=metric_name,
                    score=result.score,
                )
            except Exception as exc:
                logger.error(
                    "metric_failed",
                    evaluation_id=evaluation_id,
                    metric=metric_name,
                    error=str(exc),
                )
                # Record a failed result with score 0.
                eval_result = EvaluationResult(
                    id=uuid4(),
                    evaluation_id=eval_uuid,
                    metric_name=metric_name,
                    score=0.0,
                    threshold=metric.threshold,
                    success=False,
                    reason=f"Metric execution failed: {exc}",
                    metadata={},
                    evaluated_at=datetime.now(timezone.utc),
                )
                await eval_repo.add_result(eval_result)

        # Mark as COMPLETED.
        await eval_repo.update_status(eval_uuid, EvaluationStatus.COMPLETED)
        await session.commit()

    logger.info("evaluation_completed", evaluation_id=evaluation_id)
    return {"evaluation_id": evaluation_id, "status": "completed"}


async def _fail_evaluation(evaluation_id: str) -> None:
    """Mark an evaluation as FAILED on unrecoverable errors."""
    from uuid import UUID

    from app.infrastructure.db.engine import async_session_factory
    from app.infrastructure.db.repositories.eval_repo import EvalRepository
    from app.registry.constants import EvaluationStatus

    try:
        async with async_session_factory() as session:
            repo = EvalRepository(session)
            await repo.update_status(UUID(evaluation_id), EvaluationStatus.FAILED)
            await session.commit()
    except Exception:
        logger.error("fail_evaluation_update_failed", evaluation_id=evaluation_id)

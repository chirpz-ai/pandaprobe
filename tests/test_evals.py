"""Unit tests for the evaluation domain (no database or LLM calls)."""

from datetime import datetime, timezone
from uuid import uuid4

from app.core.evals.entities import Evaluation, EvaluationResult
from app.core.evals.metrics import get_metric, list_metrics
from app.core.evals.metrics.base import MetricResult
from app.core.evals.metrics.task_completion.schema import (
    TaskAndOutcome,
    TaskCompletionVerdict,
)
from app.core.evals.metrics.task_completion.template import TaskCompletionTemplate
from app.registry.constants import EvaluationStatus


def test_list_metrics_includes_task_completion() -> None:
    metrics = list_metrics()
    assert "task_completion" in metrics


def test_get_metric_returns_class() -> None:
    cls = get_metric("task_completion")
    assert cls.name == "task_completion"


def test_evaluation_entity_creation() -> None:
    evaluation = Evaluation(
        id=uuid4(),
        trace_id=uuid4(),
        org_id=uuid4(),
        metric_names=["task_completion"],
        status=EvaluationStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    assert evaluation.status == EvaluationStatus.PENDING
    assert evaluation.results == []


def test_evaluation_result_entity() -> None:
    result = EvaluationResult(
        id=uuid4(),
        evaluation_id=uuid4(),
        metric_name="task_completion",
        score=0.85,
        threshold=0.5,
        success=True,
        reason="Task was mostly completed.",
        evaluated_at=datetime.now(timezone.utc),
    )
    assert result.score == 0.85
    assert result.success is True


def test_metric_result_model() -> None:
    result = MetricResult(score=0.7, reason="Good", metadata={"key": "val"})
    assert result.score == 0.7


def test_task_and_outcome_schema() -> None:
    data = TaskAndOutcome(task="book a flight", outcome="found 2 flights")
    assert data.task == "book a flight"


def test_task_completion_verdict_schema() -> None:
    verdict = TaskCompletionVerdict(verdict=0.9, reason="Nearly perfect")
    assert verdict.verdict == 0.9


def test_extract_template_produces_string() -> None:
    trace = {"trace_id": "abc", "name": "test", "spans": []}
    prompt = TaskCompletionTemplate.extract_task_and_outcome(trace)
    assert "task" in prompt
    assert "outcome" in prompt


def test_verdict_template_produces_string() -> None:
    prompt = TaskCompletionTemplate.generate_verdict(
        task="Plan a trip",
        actual_outcome="Found flights and hotels",
    )
    assert "Plan a trip" in prompt
    assert "verdict" in prompt

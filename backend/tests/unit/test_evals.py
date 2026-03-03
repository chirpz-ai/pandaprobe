"""Unit tests for the evaluation domain layer (no DB or LLM calls)."""

from datetime import datetime, timezone
from uuid import uuid4

from app.core.evals.entities import EvalRun, TraceScore
from app.core.evals.metrics import get_metric, get_metric_info, list_metrics
from app.core.evals.metrics.base import MetricResult
from app.registry.constants import EvaluationStatus, ScoreDataType, ScoreSource, ScoreStatus


ALL_METRIC_NAMES = [
    "argument_correctness",
    "plan_adherence",
    "plan_quality",
    "step_efficiency",
    "task_completion",
    "tool_correctness",
]


def test_list_metrics_returns_all_six():
    names = list_metrics()
    assert names == ALL_METRIC_NAMES


def test_get_metric_returns_class():
    cls = get_metric("task_completion")
    assert cls.name == "task_completion"


def test_get_metric_info_returns_dict():
    info = get_metric_info("task_completion")
    assert info["name"] == "task_completion"
    assert "description" in info
    assert info["category"] == "trace"
    assert info["default_threshold"] == 0.5


def test_task_completion_attributes():
    cls = get_metric("task_completion")
    instance = cls()
    assert instance.name == "task_completion"
    assert instance.category == "trace"
    assert instance.threshold == 0.5
    assert instance.description != ""


def test_tool_correctness_attributes():
    cls = get_metric("tool_correctness")
    instance = cls()
    assert instance.name == "tool_correctness"
    assert instance.category == "trace"
    assert instance.threshold == 0.5
    assert instance.description != ""


def test_argument_correctness_attributes():
    cls = get_metric("argument_correctness")
    instance = cls()
    assert instance.name == "argument_correctness"
    assert instance.category == "trace"


def test_step_efficiency_attributes():
    cls = get_metric("step_efficiency")
    instance = cls()
    assert instance.name == "step_efficiency"
    assert instance.category == "trace"


def test_plan_adherence_attributes():
    cls = get_metric("plan_adherence")
    instance = cls()
    assert instance.name == "plan_adherence"
    assert instance.category == "trace"


def test_plan_quality_attributes():
    cls = get_metric("plan_quality")
    instance = cls()
    assert instance.name == "plan_quality"
    assert instance.category == "trace"


def test_trace_score_creation():
    now = datetime.now(timezone.utc)
    score = TraceScore(
        id=uuid4(),
        trace_id=uuid4(),
        project_id=uuid4(),
        name="task_completion",
        data_type=ScoreDataType.NUMERIC,
        value="0.85",
        source=ScoreSource.AUTOMATED,
        created_at=now,
        updated_at=now,
    )
    assert score.name == "task_completion"
    assert score.value == "0.85"
    assert score.source == ScoreSource.AUTOMATED


def test_trace_score_boolean():
    now = datetime.now(timezone.utc)
    score = TraceScore(
        id=uuid4(),
        trace_id=uuid4(),
        project_id=uuid4(),
        name="is_correct",
        data_type=ScoreDataType.BOOLEAN,
        value="true",
        source=ScoreSource.ANNOTATION,
        created_at=now,
        updated_at=now,
    )
    assert score.data_type == ScoreDataType.BOOLEAN


def test_trace_score_categorical():
    now = datetime.now(timezone.utc)
    score = TraceScore(
        id=uuid4(),
        trace_id=uuid4(),
        project_id=uuid4(),
        name="quality",
        data_type=ScoreDataType.CATEGORICAL,
        value="PASS",
        source=ScoreSource.PROGRAMMATIC,
        created_at=now,
        updated_at=now,
    )
    assert score.data_type == ScoreDataType.CATEGORICAL
    assert score.value == "PASS"


def test_eval_run_creation():
    now = datetime.now(timezone.utc)
    run = EvalRun(
        id=uuid4(),
        project_id=uuid4(),
        metric_names=["task_completion", "tool_correctness"],
        status=EvaluationStatus.PENDING,
        total_traces=10,
        created_at=now,
    )
    assert run.status == EvaluationStatus.PENDING
    assert len(run.metric_names) == 2
    assert run.total_traces == 10
    assert run.sampling_rate == 1.0


def test_metric_result_model():
    result = MetricResult(score=0.75, reason="Good result", metadata={"key": "value"})
    assert result.score == 0.75
    assert result.reason == "Good result"
    assert result.metadata == {"key": "value"}


def test_score_source_values():
    assert ScoreSource.AUTOMATED == "AUTOMATED"
    assert ScoreSource.ANNOTATION == "ANNOTATION"
    assert ScoreSource.PROGRAMMATIC == "PROGRAMMATIC"


def test_score_status_values():
    assert ScoreStatus.SUCCESS == "SUCCESS"
    assert ScoreStatus.FAILED == "FAILED"
    assert ScoreStatus.PENDING == "PENDING"


def test_score_data_type_values():
    assert ScoreDataType.NUMERIC == "NUMERIC"
    assert ScoreDataType.BOOLEAN == "BOOLEAN"
    assert ScoreDataType.CATEGORICAL == "CATEGORICAL"


def test_evaluation_status_unchanged():
    assert EvaluationStatus.PENDING == "PENDING"
    assert EvaluationStatus.RUNNING == "RUNNING"
    assert EvaluationStatus.COMPLETED == "COMPLETED"
    assert EvaluationStatus.FAILED == "FAILED"

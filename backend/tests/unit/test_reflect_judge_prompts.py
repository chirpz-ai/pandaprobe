"""Reflect rule and memory operations stay neutral without concealing task mistakes."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.evals.metrics.trace.argument_correctness.metric import ArgumentCorrectnessMetric
from app.core.evals.metrics.trace.argument_correctness.schema import (
    ArgumentCorrectnessReason,
    ArgumentVerdicts,
    ToolCallContext,
)
from app.core.evals.metrics.trace.argument_correctness.template import ArgumentCorrectnessTemplate
from app.core.evals.metrics.trace.confidence.template import ConfidenceTemplate
from app.core.evals.metrics.trace.plan_adherence.template import PlanAdherenceTemplate
from app.core.evals.metrics.trace.step_efficiency.template import StepEfficiencyTemplate
from app.core.evals.metrics.trace.task_completion.template import TaskCompletionTemplate
from app.core.evals.metrics.trace.tool_correctness.template import ToolCorrectnessTemplate
from app.core.evals.metrics.utils import REFLECT_TOOL_GUIDANCE
from app.core.traces.entities import Trace


@pytest.mark.parametrize("name", ["reflect_bash", "mcp__pandaprobe_reflect__reflect_bash", "Bash"])
def test_extraction_preserves_task_directed_commands_and_failures(name):
    """A misleading name must not cause evidence to disappear before judging."""
    command = "cp /rules/draft.md /customer/report.md"
    trace = {
        "input": {"messages": [{"role": "user", "content": "Save the customer report"}]},
        "spans": [
            {
                "kind": "TOOL",
                "name": name,
                "input": {"command": command},
                "output": {"exit_code": 1, "stderr": "No such directory"},
            }
        ],
    }
    for prompt in (
        ToolCorrectnessTemplate.extract_tool_usage(trace),
        ArgumentCorrectnessTemplate.extract_tool_calls(trace),
        TaskCompletionTemplate.extract_task_and_outcome(trace),
    ):
        assert json.dumps(trace, indent=2, default=str) in prompt
        assert name in prompt and command in prompt and "No such directory" in prompt


@pytest.mark.parametrize(
    ("template", "stage"),
    [
        (TaskCompletionTemplate, "extract"),
        (ToolCorrectnessTemplate, "score"),
        (ArgumentCorrectnessTemplate, "verdicts"),
        (StepEfficiencyTemplate, "score"),
        (ConfidenceTemplate, "evaluate"),
        (PlanAdherenceTemplate, "score"),
    ],
)
def test_judges_receive_one_optional_neutrality_note(template, stage):
    """Keep the policy consistent even on traces without Reflect calls."""
    prompt = template.get_prompt_preview()[stage]
    assert prompt.count(REFLECT_TOOL_GUIDANCE) == 1
    assert "Reflect is optional" in prompt
    policy = " ".join(prompt.split())
    assert "Reflect rule and memory operations" in policy
    assert "no credit or penalty" in policy
    assert "frequency, or cost" in policy
    assert "does not exempt mistakes" in prompt
    assert "total operational efficiency" not in prompt
    assert "unproductive administration" not in prompt


def test_memory_only_outcome_does_not_demonstrate_task_completion():
    prompt = TaskCompletionTemplate.generate_verdict("Save a report", "Wrote a proposed rule")
    assert "Reflect rule and memory operations alone show no task progress" in prompt
    assert "not proof that a task failure was corrected" in prompt


@pytest.fixture
def trace():
    return Trace(trace_id=uuid4(), project_id=uuid4(), name="refund", started_at=datetime.now(timezone.utc))


@pytest.mark.parametrize("neutral_count", [0, 1, 10])
@pytest.mark.parametrize(("task_verdicts", "expected"), [(["yes"], 1.0), (["no"], 0.0), (["yes", "no"], 0.5)])
async def test_memory_calls_do_not_change_argument_score(trace, neutral_count, task_verdicts, expected):
    """Extra memory calls cannot mask task errors or reduce a correct task's score."""
    calls = [
        {"name": "reflect_bash", "parameters": {"command": "cat /rules/refunds.md"}} for _ in range(neutral_count)
    ]
    calls += [
        {"name": "refund", "parameters": {"amount": 6500}}
        if verdict == "yes"
        else {"name": "reflect_bash", "parameters": {"command": "echo refunded > /customer/ledger"}}
        for verdict in task_verdicts
    ]
    verdicts = [
        *({"verdict": "neutral", "reason": "Read learned guidance"} for _ in range(neutral_count)),
        *(
            {"verdict": verdict, "reason": "Wrong task arguments" if verdict == "no" else None}
            for verdict in task_verdicts
        ),
    ]
    llm = AsyncMock()
    llm.generate_structured.side_effect = [
        ToolCallContext(user_input="Refund the order", tool_calls=calls),
        ArgumentVerdicts(verdicts=verdicts),
        ArgumentCorrectnessReason(reason="Task argument assessment"),
    ]
    result = await ArgumentCorrectnessMetric().evaluate(trace, llm, threshold=0.75, model="test-judge")
    assert result.score == expected
    assert result.metadata["success"] == (expected >= 0.75)
    assert result.metadata["verdicts"] == verdicts
    assert result.reason == "Task argument assessment"
    reason_prompt = llm.generate_structured.call_args.kwargs["prompt"]
    assert "Read learned guidance" not in reason_prompt
    assert ("Wrong task arguments" in reason_prompt) == ("no" in task_verdicts)
    assert all(call.kwargs["model"] == "test-judge" for call in llm.generate_structured.call_args_list)


@pytest.mark.parametrize("name", ["reflect_bash", "mcp__pandaprobe_reflect__reflect_bash"])
async def test_memory_only_arguments_are_reported_as_not_applicable(trace, name):
    llm = AsyncMock()
    verdict = {"verdict": "neutral", "reason": "Maintain learned guidance"}
    llm.generate_structured.side_effect = [
        ToolCallContext(user_input="Refund the order", tool_calls=[{"name": name, "parameters": {}}]),
        ArgumentVerdicts(verdicts=[verdict]),
    ]
    result = await ArgumentCorrectnessMetric().evaluate(trace, llm)
    # Preserve the metric's existing nothing-to-evaluate convention, with an explicit reason.
    assert result.score == 1.0
    assert result.reason == "Only Reflect rule and memory operations; no task-directed arguments to evaluate."
    assert result.metadata["verdicts"] == [verdict]
    assert llm.generate_structured.await_count == 2


async def test_no_tool_arguments_keeps_existing_behavior(trace):
    llm = AsyncMock()
    llm.generate_structured.return_value = ToolCallContext(user_input="Answer the question", tool_calls=[])
    result = await ArgumentCorrectnessMetric().evaluate(trace, llm)
    assert result.score == 1.0
    assert result.reason == "No tool calls in trace; nothing to evaluate."
    assert result.metadata["verdicts"] == []
    llm.generate_structured.assert_awaited_once()

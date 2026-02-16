"""CrewAI trace transformer.

CrewAI organises work around Crews, Agents, and Tasks.  This
transformer maps that hierarchy into Opentracer's universal Span tree:

- **Crew**      → root Span  (kind=AGENT)
- **Task**      → child Span (kind=AGENT)
- **Tool step** → child Span (kind=TOOL)
- **LLM step**  → child Span (kind=LLM)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from app.core.traces.entities import Span, Trace
from app.integrations import register_integration
from app.integrations._utils import parse_timestamp
from app.integrations.base import BaseTraceTransformer
from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus


@register_integration("crewai")
class CrewAITransformer(BaseTraceTransformer):
    """Transform CrewAI execution traces into universal traces."""

    @property
    def framework_name(self) -> str:
        """Return the framework identifier."""
        return "crewai"

    def validate_payload(self, raw: dict[str, Any]) -> bool:
        """Detect CrewAI payloads by crew-specific keys."""
        return "crew" in raw or ("tasks" in raw and "agents" in raw)

    def transform(self, raw: dict[str, Any], org_id: UUID) -> Trace:
        """Convert a CrewAI execution trace into a universal Trace."""
        trace_id = uuid4()
        spans: list[Span] = []

        crew = raw.get("crew", {})
        crew_span_id = uuid4()

        spans.append(
            Span(
                span_id=crew_span_id,
                trace_id=trace_id,
                name=crew.get("name", "crewai-crew"),
                kind=SpanKind.AGENT,
                status=SpanStatusCode.OK if raw.get("status") != "error" else SpanStatusCode.ERROR,
                input=raw.get("input"),
                output=raw.get("output"),
                metadata={"source": "crewai", "crew_id": crew.get("id")},
                started_at=parse_timestamp(raw.get("start_time")),
                ended_at=parse_timestamp(raw.get("end_time")),
            )
        )

        for task in raw.get("tasks", []):
            task_span_id = uuid4()
            token_usage = _extract_task_token_usage(task)

            spans.append(
                Span(
                    span_id=task_span_id,
                    trace_id=trace_id,
                    parent_span_id=crew_span_id,
                    name=task.get("description", "task"),
                    kind=SpanKind.AGENT,
                    status=SpanStatusCode.OK if task.get("status") != "error" else SpanStatusCode.ERROR,
                    input=task.get("input"),
                    output=task.get("output"),
                    token_usage=token_usage,
                    metadata={"agent": task.get("agent")},
                    started_at=parse_timestamp(task.get("start_time")),
                    ended_at=parse_timestamp(task.get("end_time")),
                )
            )

            for step in task.get("steps", []):
                step_kind = SpanKind.TOOL if step.get("type") == "tool" else SpanKind.LLM
                step_token = None
                if step.get("token_usage") and isinstance(step["token_usage"], dict):
                    step_token = step["token_usage"]

                spans.append(
                    Span(
                        span_id=uuid4(),
                        trace_id=trace_id,
                        parent_span_id=task_span_id,
                        name=step.get("name", step.get("type", "step")),
                        kind=step_kind,
                        status=SpanStatusCode.OK if step.get("error") is None else SpanStatusCode.ERROR,
                        input=step.get("input"),
                        output=step.get("output"),
                        model=step.get("model"),
                        token_usage=step_token,
                        metadata={},
                        started_at=parse_timestamp(step.get("start_time")),
                        ended_at=parse_timestamp(step.get("end_time")),
                    )
                )

        return Trace(
            trace_id=trace_id,
            org_id=org_id,
            name=crew.get("name", "crewai-trace"),
            status=TraceStatus.COMPLETED if raw.get("status") != "error" else TraceStatus.ERROR,
            input=raw.get("input"),
            output=raw.get("output"),
            metadata={"source": "crewai"},
            started_at=parse_timestamp(raw.get("start_time")),
            ended_at=parse_timestamp(raw.get("end_time")),
            spans=spans,
        )


def _extract_task_token_usage(task: dict[str, Any]) -> dict[str, int] | None:
    """Aggregate token usage across all steps in a task."""
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    found = False
    for step in task.get("steps", []):
        tu = step.get("token_usage")
        if tu and isinstance(tu, dict):
            found = True
            total["prompt_tokens"] += tu.get("prompt_tokens", 0)
            total["completion_tokens"] += tu.get("completion_tokens", 0)
            total["total_tokens"] += tu.get("total_tokens", 0)
    return total if found else None

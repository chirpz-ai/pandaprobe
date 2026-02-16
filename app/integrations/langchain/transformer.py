"""LangChain trace transformer.

Normalises LangChain callback-style traces (runs / child_runs) into
Opentracer's universal Trace / Span format.

LangChain traces arrive as a nested ``Run`` object with keys like
``name``, ``run_type``, ``inputs``, ``outputs``, ``start_time``,
``end_time``, and ``child_runs``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from app.core.traces.entities import Span, Trace
from app.integrations import register_integration
from app.integrations._utils import parse_timestamp, safe_get
from app.integrations.base import BaseTraceTransformer
from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus

_RUN_TYPE_TO_SPAN_KIND: dict[str, SpanKind] = {
    "chain": SpanKind.CHAIN,
    "llm": SpanKind.LLM,
    "tool": SpanKind.TOOL,
    "retriever": SpanKind.RETRIEVER,
    "embedding": SpanKind.EMBEDDING,
    "agent": SpanKind.AGENT,
}


@register_integration("langchain")
class LangChainTransformer(BaseTraceTransformer):
    """Transform LangChain run dicts into universal traces."""

    @property
    def framework_name(self) -> str:
        """Return the framework identifier."""
        return "langchain"

    def validate_payload(self, raw: dict[str, Any]) -> bool:
        """Check for LangChain-specific keys (``run_type`` + ``child_runs``)."""
        return "run_type" in raw and "child_runs" in raw

    def transform(self, raw: dict[str, Any], org_id: UUID) -> Trace:
        """Convert a LangChain run tree into a Trace with nested Spans."""
        trace_id = uuid4()
        spans: list[Span] = []
        self._walk(raw, trace_id=trace_id, parent_span_id=None, spans=spans)

        return Trace(
            trace_id=trace_id,
            org_id=org_id,
            name=raw.get("name", "langchain-trace"),
            status=TraceStatus.COMPLETED if raw.get("error") is None else TraceStatus.ERROR,
            input=raw.get("inputs"),
            output=raw.get("outputs"),
            metadata={"source": "langchain", "tags": raw.get("tags", [])},
            started_at=parse_timestamp(raw.get("start_time")),
            ended_at=parse_timestamp(raw.get("end_time")),
            spans=spans,
        )

    def _walk(
        self,
        run: dict[str, Any],
        trace_id: UUID,
        parent_span_id: UUID | None,
        spans: list[Span],
    ) -> None:
        """Recursively flatten the run tree into a flat span list."""
        span_id = uuid4()
        run_type = run.get("run_type", "chain")

        model_name = safe_get(run, "extra", "invocation_params", "model_name")
        token_usage_raw = safe_get(run, "extra", "token_usage")
        token_usage: dict[str, int] | None = None
        if token_usage_raw and isinstance(token_usage_raw, dict):
            token_usage = {
                "prompt_tokens": token_usage_raw.get("prompt_tokens", 0),
                "completion_tokens": token_usage_raw.get("completion_tokens", 0),
                "total_tokens": token_usage_raw.get("total_tokens", 0),
            }

        spans.append(
            Span(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                name=run.get("name", run_type),
                kind=_RUN_TYPE_TO_SPAN_KIND.get(run_type, SpanKind.OTHER),
                status=SpanStatusCode.ERROR if run.get("error") else SpanStatusCode.OK,
                input=run.get("inputs"),
                output=run.get("outputs"),
                model=model_name,
                token_usage=token_usage,
                metadata={
                    "run_type": run_type,
                    "tags": run.get("tags", []),
                },
                started_at=parse_timestamp(run.get("start_time")),
                ended_at=parse_timestamp(run.get("end_time")),
            )
        )

        for child in run.get("child_runs", []):
            self._walk(child, trace_id=trace_id, parent_span_id=span_id, spans=spans)

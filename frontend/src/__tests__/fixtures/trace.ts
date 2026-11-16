import type { SpanResponse, TraceResponse } from "@/lib/api/types";

export function makeSpan(overrides: Partial<SpanResponse> = {}): SpanResponse {
  return {
    span_id: "root",
    trace_id: "trace-1",
    parent_span_id: null,
    name: "Agent",
    kind: "AGENT",
    status: "OK",
    input: null,
    output: null,
    model: null,
    token_usage: null,
    metadata: {},
    started_at: "2026-08-01T00:00:00Z",
    ended_at: "2026-08-01T00:00:08Z",
    latency_ms: 8000,
    error: null,
    completion_start_time: null,
    time_to_first_token_ms: null,
    model_parameters: null,
    cost: null,
    ...overrides,
  };
}

export function makeTrace(
  overrides: Partial<TraceResponse> = {},
): TraceResponse {
  return {
    trace_id: "trace-1",
    project_id: "project-1",
    name: "Support workflow",
    status: "COMPLETED",
    input: { messages: [{ role: "user", content: "Find my order" }] },
    output: {
      messages: [{ role: "assistant", content: "Your **order** has shipped." }],
    },
    metadata: {},
    started_at: "2026-08-01T00:00:00Z",
    ended_at: "2026-08-01T00:00:08Z",
    session_id: null,
    user_id: null,
    tags: [],
    environment: null,
    release: null,
    total_tokens: 1234,
    total_cost: 0,
    spans: [
      makeSpan(),
      makeSpan({
        span_id: "llm",
        parent_span_id: "root",
        name: "ChatOpenAI",
        kind: "LLM",
        started_at: "2026-08-01T00:00:02Z",
        ended_at: "2026-08-01T00:00:04Z",
        latency_ms: 2000,
        input: { messages: [{ role: "user", content: "Find my order" }] },
        output: { role: "assistant", content: "Your order has shipped." },
        model: "test-model",
      }),
      makeSpan({
        span_id: "tool",
        parent_span_id: "root",
        name: "Lookup order",
        kind: "TOOL",
        started_at: "2026-08-01T00:00:04Z",
        ended_at: "2026-08-01T00:00:04Z",
        latency_ms: 0,
        output: { shipped: true },
      }),
    ],
    ...overrides,
  };
}

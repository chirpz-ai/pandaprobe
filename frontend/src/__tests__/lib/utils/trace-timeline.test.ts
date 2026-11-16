import {
  buildTree,
  getTimeline,
  getBarPosition,
  spanDuration,
} from "@/lib/utils/trace-timeline";
import { makeTrace, makeSpan } from "../../fixtures/trace";

describe("trace timing", () => {
  it("sorts siblings by time, attaches out-of-order children, and retains orphans", () => {
    const trace = makeTrace();
    const roots = buildTree([
      trace.spans[2],
      trace.spans[1],
      trace.spans[0],
      makeSpan({ span_id: "orphan", parent_span_id: "missing" }),
    ]);
    expect(roots.map((span) => span.span_id)).toEqual(["root", "orphan"]);
    expect(roots[0].children.map((span) => span.span_id)).toEqual([
      "llm",
      "tool",
    ]);
  });
  it("breaks malformed cycles so spans remain reachable", () => {
    const roots = buildTree([
      makeSpan({ span_id: "a", parent_span_id: "b" }),
      makeSpan({ span_id: "b", parent_span_id: "a" }),
      makeSpan({ span_id: "c", parent_span_id: "c" }),
    ]);
    expect(roots.map((span) => span.span_id)).toEqual(["a", "b", "c"]);
  });
  it("includes spans outside trace boundaries and computes missing duration from timestamps", () => {
    const trace = makeTrace({
      spans: [
        makeSpan({
          started_at: "2026-07-31T23:59:59Z",
          ended_at: "2026-08-01T00:00:10Z",
          latency_ms: null,
        }),
      ],
    });
    expect(spanDuration(trace.spans[0])).toBe(11000);
    const timeline = getTimeline(trace);
    expect(timeline.start).toBe(Date.parse("2026-07-31T23:59:59Z"));
    expect(timeline.extent).toBeGreaterThanOrEqual(11000);
  });
  it("handles missing, invalid and zero-duration timing without NaN or invented duration", () => {
    const trace = makeTrace({
      started_at: null,
      ended_at: null,
      spans: [
        makeSpan({ started_at: "invalid", ended_at: null, latency_ms: null }),
      ],
    });
    const timeline = getTimeline(trace);
    expect(timeline.extent).toBeGreaterThan(0);
    expect(spanDuration(trace.spans[0])).toBeNull();
    expect(getBarPosition("invalid", null, timeline)).toBeNull();
    expect(spanDuration(makeSpan({ latency_ms: 0 }))).toBe(0);
    const instant = getTimeline(
      makeTrace({ ended_at: "2026-08-01T00:00:00Z", spans: [] }),
    );
    expect(getBarPosition("2026-08-01T00:00:00Z", 0, instant)).toEqual({
      left: 0,
      width: 0,
    });
  });
  it("uses available observations for a running trace without assigning unfinished spans a duration", () => {
    const trace = makeTrace({
      ended_at: null,
      spans: [
        makeSpan({ latency_ms: null, ended_at: null }),
        makeSpan({
          span_id: "child",
          started_at: "2026-08-01T00:00:03Z",
          ended_at: "2026-08-01T00:00:04Z",
          latency_ms: 1000,
        }),
      ],
    });
    expect(getTimeline(trace).extent).toBe(4000);
    expect(spanDuration(trace.spans[0])).toBeNull();
  });
});

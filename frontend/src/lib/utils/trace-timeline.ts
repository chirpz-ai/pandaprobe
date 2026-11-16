import type { SpanResponse, TraceResponse } from "@/lib/api/types";

export interface SpanNode extends SpanResponse {
  children: SpanNode[];
}

export function timestamp(value: string | null): number | null {
  const time = value ? Date.parse(value) : NaN;
  return Number.isFinite(time) ? time : null;
}

export function spanDuration(span: SpanResponse): number | null {
  if (span.latency_ms != null && Number.isFinite(span.latency_ms)) {
    return Math.max(0, span.latency_ms);
  }
  const start = timestamp(span.started_at);
  const end = timestamp(span.ended_at);
  return start != null && end != null ? Math.max(0, end - start) : null;
}

/** Preserve hierarchy even for out-of-order or orphaned spans; break cycles. */
export function buildTree(spans: SpanResponse[]): SpanNode[] {
  const nodes = new Map(
    spans.map((span) => [span.span_id, { ...span, children: [] } as SpanNode]),
  );
  const roots: SpanNode[] = [];
  for (const node of nodes.values()) {
    const ancestors = new Set([node.span_id]);
    let parent = node.parent_span_id;
    while (parent && nodes.has(parent) && !ancestors.has(parent)) {
      ancestors.add(parent);
      parent = nodes.get(parent)!.parent_span_id;
    }
    if (parent && ancestors.has(parent)) {
      roots.push(node);
    } else if (node.parent_span_id && nodes.has(node.parent_span_id)) {
      nodes.get(node.parent_span_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  const sort = (siblings: SpanNode[]) => {
    siblings.sort(
      (a, b) =>
        (timestamp(a.started_at) ?? Infinity) -
        (timestamp(b.started_at) ?? Infinity),
    );
    siblings.forEach((node) => sort(node.children));
  };
  sort(roots);
  return roots;
}

export function getTimeline(trace: TraceResponse) {
  const times: number[] = [];
  for (const value of [trace.started_at, trace.ended_at]) {
    const time = timestamp(value);
    if (time != null) times.push(time);
  }
  for (const span of trace.spans) {
    const start = timestamp(span.started_at);
    const end = timestamp(span.ended_at);
    if (start != null) {
      times.push(start, start + (spanDuration(span) ?? 0));
    }
    if (end != null) times.push(end);
  }
  const start = times.length ? Math.min(...times) : 0;
  const observedEnd = times.length ? Math.max(...times) : start;
  const duration = Math.max(1, observedEnd - start);
  const roughStep = duration / 5;
  const magnitude = 10 ** Math.floor(Math.log10(roughStep));
  const step =
    ([1, 2, 5, 10].find((n) => n * magnitude >= roughStep) ?? 10) * magnitude;
  const extent = Math.ceil(duration / step) * step;
  const ticks = Array.from(
    { length: Math.round(extent / step) + 1 },
    (_, i) => i * step,
  );
  return { start, observedEnd, extent, ticks };
}

export type Timeline = ReturnType<typeof getTimeline>;

export function getBarPosition(
  startedAt: string | null,
  duration: number | null,
  timeline: Timeline,
) {
  const start = timestamp(startedAt);
  if (start == null) return null;
  const left = Math.max(
    0,
    Math.min(100, ((start - timeline.start) / timeline.extent) * 100),
  );
  const width = Math.max(
    0,
    Math.min(100 - left, ((duration ?? 0) / timeline.extent) * 100),
  );
  return { left, width };
}

export function formatTick(ms: number, extent: number): string {
  return extent >= 1000
    ? `${Number((ms / 1000).toFixed(3))}s`
    : `${Number(ms.toFixed(2))}ms`;
}

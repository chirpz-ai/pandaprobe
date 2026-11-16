"use client";

import { useMemo, useState, type CSSProperties } from "react";
import {
  ChevronRight,
  ChevronDown,
  Bot,
  Wrench,
  Sparkles,
  Search,
  Link,
  Grid3X3,
  Circle,
  Activity,
} from "lucide-react";
import type { TraceResponse } from "@/lib/api/types";
import { formatDuration } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";
import {
  getTimeline,
  getBarPosition,
  spanDuration,
  timestamp,
  formatTick,
  type SpanNode,
  type Timeline,
} from "@/lib/utils/trace-timeline";

const KINDS = {
  AGENT: { icon: Bot, color: "#60a5fa" },
  TOOL: { icon: Wrench, color: "#fbbf24" },
  LLM: { icon: Sparkles, color: "#a78bfa" },
  RETRIEVER: { icon: Search, color: "#4ade80" },
  CHAIN: { icon: Link, color: "#38bdf8" },
  EMBEDDING: { icon: Grid3X3, color: "#22d3ee" },
  OTHER: { icon: Circle, color: "#94a3b8" },
  TRACE: { icon: Activity, color: "#38bdf8" },
};

interface Props {
  trace: TraceResponse;
  tree: SpanNode[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function WaterfallTree({ trace, tree, selectedId, onSelect }: Props) {
  const timeline = useMemo(() => getTimeline(trace), [trace]);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const rows: { node: SpanNode; depth: number }[] = [];
  const visit = (nodes: SpanNode[], depth: number) => {
    for (const node of nodes) {
      rows.push({ node, depth });
      if (!collapsed.has(node.span_id)) visit(node.children, depth + 1);
    }
  };
  if (!collapsed.has("trace")) visit(tree, 1);
  const toggle = (id: string) =>
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const traceStart = timestamp(trace.started_at);
  const traceEnd = timestamp(trace.ended_at);
  const traceDuration =
    traceStart != null && traceEnd != null
      ? Math.max(0, traceEnd - traceStart)
      : null;

  return (
    <div className="min-w-0 min-h-full">
      <div className="sticky top-0 z-20 bg-surface border-b border-border">
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-3 text-[10px] font-mono uppercase tracking-wider text-text-muted">
          <span className="hidden lg:inline">
            Waterfall · {trace.spans.length} spans
          </span>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setCollapsed(new Set())}
              className="hover:text-text focus-visible:outline focus-visible:outline-primary"
            >
              Expand all
            </button>
            <button
              type="button"
              onClick={() =>
                setCollapsed(
                  new Set([
                    "trace",
                    ...trace.spans.map((span) => span.span_id),
                  ]),
                )
              }
              className="hover:text-text focus-visible:outline focus-visible:outline-primary"
            >
              Collapse all
            </button>
          </div>
        </div>
        <div
          className="relative h-7 ml-3 mr-10 text-[10px] font-mono text-text-muted"
          aria-label="Elapsed time"
        >
          {timeline.ticks.map((tick, i) => (
            <span
              key={tick}
              className="absolute bottom-1 tabular-nums"
              style={{
                left: `${(tick / timeline.extent) * 100}%`,
                transform:
                  i === 0
                    ? undefined
                    : i === timeline.ticks.length - 1
                      ? "translateX(-100%)"
                      : "translateX(-50%)",
              }}
            >
              {formatTick(tick, timeline.extent)}
            </span>
          ))}
        </div>
      </div>
      <div className="relative py-1">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 left-3 right-10"
        >
          {timeline.ticks.map((tick) => (
            <div
              key={tick}
              className="absolute inset-y-0 border-l border-border/60"
              style={{ left: `${(tick / timeline.extent) * 100}%` }}
            />
          ))}
        </div>
        <TimelineRow
          id="trace"
          name={trace.name}
          kind="TRACE"
          status={trace.status}
          startedAt={trace.started_at}
          duration={traceDuration}
          depth={0}
          timeline={timeline}
          selected={selectedId === "trace"}
          onSelect={onSelect}
          hasChildren={tree.length > 0}
          expanded={!collapsed.has("trace")}
          onToggle={toggle}
        />
        {rows.map(({ node, depth }) => (
          <TimelineRow
            key={node.span_id}
            id={node.span_id}
            name={node.name}
            kind={node.kind}
            model={node.model}
            status={node.status}
            startedAt={node.started_at}
            duration={spanDuration(node)}
            depth={depth}
            timeline={timeline}
            selected={selectedId === node.span_id}
            onSelect={onSelect}
            hasChildren={node.children.length > 0}
            expanded={!collapsed.has(node.span_id)}
            onToggle={toggle}
          />
        ))}
        {trace.spans.length === 0 && (
          <p className="p-6 text-center text-xs font-mono text-text-muted">
            No spans recorded
          </p>
        )}
      </div>
    </div>
  );
}

function TimelineRow({
  id,
  name,
  kind,
  model,
  status,
  startedAt,
  duration,
  depth,
  timeline,
  selected,
  onSelect,
  hasChildren,
  expanded,
  onToggle,
}: {
  id: string;
  name: string;
  kind: keyof typeof KINDS;
  model?: string | null;
  status: string;
  startedAt: string | null;
  duration: number | null;
  depth: number;
  timeline: Timeline;
  selected: boolean;
  onSelect: (id: string) => void;
  hasChildren: boolean;
  expanded: boolean;
  onToggle: (id: string) => void;
}) {
  const config = KINDS[kind] ?? KINDS.OTHER;
  const Icon = config.icon;
  const position = getBarPosition(startedAt, duration, timeline);
  const isError = status === "ERROR" || status === "FAILED";
  const color = isError ? "var(--color-error)" : config.color;
  const tooltip = `${name} · ${kind}${model ? ` · ${model}` : ""}\n${formatDuration(duration)} · ${status}${position ? ` · +${formatDuration(timestamp(startedAt)! - timeline.start)}` : " · Start time unavailable"}`;
  return (
    <div
      className={cn(
        "relative flex h-11 items-stretch border-l-2 border-transparent hover:bg-surface-hi/50",
        selected && "bg-surface-hi/70",
      )}
      style={selected ? { borderLeftColor: color } : undefined}
    >
      <button
        type="button"
        onClick={() => onSelect(id)}
        aria-pressed={selected}
        aria-label={`${name} ${kind} ${formatDuration(duration)}${isError ? " Error" : ""}`}
        title={tooltip}
        className="relative flex-1 min-w-0 ml-2.5 mr-1 text-left focus-visible:outline focus-visible:outline-primary focus-visible:-outline-offset-2"
      >
        {position && (
          <span
            aria-hidden="true"
            data-timeline-bar={id}
            className={cn(
              "absolute top-1.5 bottom-1.5 rounded-sm border-l-2",
              duration == null && "border border-dashed",
            )}
            style={
              {
                left: `min(${position.left}%, calc(100% - 2px))`,
                width: `${position.width}%`,
                minWidth: 2,
                backgroundColor: `color-mix(in srgb, ${color} ${selected ? 35 : 20}%, transparent)`,
                borderColor: color,
              } as CSSProperties
            }
          />
        )}
        <span
          className="absolute inset-y-0 flex items-center gap-1.5 pr-1 max-w-full"
          style={{
            left: `clamp(0px, calc(${position?.left ?? 0}% + ${Math.min(depth, 5) * 8 + 6}px), max(0px, calc(100% - 250px)))`,
            right: 0,
          }}
        >
          <Icon className="h-3.5 w-3.5 shrink-0" style={{ color }} />
          <span className="text-xs font-mono text-text truncate">{name}</span>
          <span
            className="text-[9px] font-mono shrink-0 uppercase"
            style={{ color }}
          >
            {kind}
          </span>
          <span className="text-[10px] font-mono text-text-dim shrink-0 tabular-nums">
            {formatDuration(duration)}
          </span>
          {isError && <span className="text-[9px] text-error">Error</span>}
        </span>
      </button>
      <div className="flex w-9 shrink-0 items-center justify-center">
        {hasChildren && (
          <button
            type="button"
            onClick={() => onToggle(id)}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${name}`}
            aria-expanded={expanded}
            className="flex h-9 w-8 items-center justify-center text-text-muted hover:text-text focus-visible:outline focus-visible:outline-primary"
          >
            {expanded ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>
        )}
      </div>
    </div>
  );
}

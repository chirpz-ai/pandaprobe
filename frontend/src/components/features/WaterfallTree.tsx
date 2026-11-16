"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import type { TraceResponse } from "@/lib/api/types";
import { formatDuration } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";
import {
  spanDuration,
  timestamp,
  type SpanNode,
} from "@/lib/utils/trace-timeline";
import { SPAN_KINDS } from "./span-kind";

interface WaterfallTreeProps {
  trace: TraceResponse;
  tree: SpanNode[];
  collapsed: Set<string>;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
}

export function WaterfallTree({
  trace,
  tree,
  collapsed,
  selectedId,
  onSelect,
  onToggle,
}: WaterfallTreeProps) {
  const rows: { node: SpanNode; branches: boolean[] }[] = [];
  const visit = (nodes: SpanNode[], ancestors: boolean[]) => {
    nodes.forEach((node, index) => {
      const branches = [...ancestors, index < nodes.length - 1];
      rows.push({ node, branches });
      if (!collapsed.has(node.span_id)) visit(node.children, branches);
    });
  };
  if (!collapsed.has("trace")) visit(tree, []);
  const start = timestamp(trace.started_at);
  const end = timestamp(trace.ended_at);

  return (
    <div className="py-1" aria-label="Span hierarchy">
      <WaterfallRow
        id="trace"
        name={trace.name}
        kind="TRACE"
        status={trace.status}
        duration={
          start != null && end != null ? Math.max(0, end - start) : null
        }
        branches={[]}
        hasChildren={tree.length > 0}
        expanded={!collapsed.has("trace")}
        selected={selectedId === "trace"}
        onSelect={onSelect}
        onToggle={onToggle}
      />
      {rows.map(({ node, branches }) => (
        <WaterfallRow
          key={node.span_id}
          id={node.span_id}
          name={node.name}
          kind={node.kind}
          model={node.model}
          status={node.status}
          duration={spanDuration(node)}
          branches={branches}
          hasChildren={node.children.length > 0}
          expanded={!collapsed.has(node.span_id)}
          selected={selectedId === node.span_id}
          onSelect={onSelect}
          onToggle={onToggle}
        />
      ))}
    </div>
  );
}

const INDENT = 18;
const ROW_HEIGHT = 36;

function WaterfallRow({
  id,
  name,
  kind,
  model,
  status,
  duration,
  branches,
  hasChildren,
  expanded,
  selected,
  onSelect,
  onToggle,
}: {
  id: string;
  name: string;
  kind: keyof typeof SPAN_KINDS;
  model?: string | null;
  status: string;
  duration: number | null;
  branches: boolean[];
  hasChildren: boolean;
  expanded: boolean;
  selected: boolean;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
}) {
  const config = SPAN_KINDS[kind] ?? SPAN_KINDS.OTHER;
  const Icon = config.icon;
  const isError = status === "ERROR" || status === "FAILED";
  const color = config.color;
  return (
    <div
      className={cn(
        "relative flex h-9 items-center pr-3 border-l-2 border-transparent hover:bg-surface-hi/60",
        selected && "bg-surface-hi",
      )}
      style={{
        paddingLeft: 12 + branches.length * INDENT,
        minWidth: 240 + branches.length * INDENT,
        borderLeftColor: selected ? color : undefined,
      }}
    >
      {branches.length > 0 && (
        <svg
          aria-hidden="true"
          className="absolute left-3 top-0 pointer-events-none text-line"
          width={branches.length * INDENT}
          height={ROW_HEIGHT}
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
        >
          {branches.map((continues, level) => {
            const x = level * INDENT + 1;
            const isBranch = level === branches.length - 1;
            return (
              <path
                key={level}
                d={
                  isBranch
                    ? `M ${x} 0 V 12 Q ${x} 18 ${x + 6} 18 H ${x + 15}${continues ? ` M ${x} 12 V ${ROW_HEIGHT}` : ""}`
                    : continues
                      ? `M ${x} 0 V ${ROW_HEIGHT}`
                      : ""
                }
              />
            );
          })}
        </svg>
      )}
      <div className="w-5 shrink-0">
        {hasChildren && (
          <button
            type="button"
            aria-label={`${expanded ? "Collapse" : "Expand"} ${name}`}
            aria-expanded={expanded}
            onClick={() => onToggle(id)}
            className="flex h-8 w-5 items-center justify-center text-text-muted hover:text-text focus-visible:outline focus-visible:outline-primary"
          >
            {expanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
        )}
      </div>
      <button
        type="button"
        aria-pressed={selected}
        aria-label={`${name} ${kind} ${formatDuration(duration)}${isError ? " Error" : ""}`}
        title={`${name} · ${kind}${model ? ` · ${model}` : ""} · ${status}`}
        onClick={() => onSelect(id)}
        className="flex h-full flex-1 min-w-0 items-center gap-2 text-left focus-visible:outline focus-visible:outline-primary focus-visible:-outline-offset-2"
      >
        <Icon className="h-3.5 w-3.5 shrink-0" style={{ color }} />
        <span className="min-w-0 flex-1 truncate text-xs font-mono text-text">
          {name}
        </span>
        <span className="shrink-0 text-compact font-mono" style={{ color }}>
          {kind}
        </span>
        {model && (
          <span className="hidden xl:inline max-w-20 truncate text-caption font-mono text-text-muted">
            {model}
          </span>
        )}
        <span className="shrink-0 text-caption font-mono text-text-dim tabular-nums">
          {formatDuration(duration)}
        </span>
        <span
          className={cn(
            "h-1.5 w-1.5 shrink-0 rounded-sm",
            isError
              ? "bg-error"
              : status === "OK" || status === "COMPLETED"
                ? "bg-success"
                : "bg-text-muted",
          )}
          aria-label={status}
          title={status}
        />
      </button>
    </div>
  );
}

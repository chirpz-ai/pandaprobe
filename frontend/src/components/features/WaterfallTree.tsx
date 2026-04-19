"use client";

import { useState, memo } from "react";
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
import type { SpanResponse, TraceResponse } from "@/lib/api/types";
import type { SpanKind } from "@/lib/api/enums";
import { SpanStatusCode } from "@/lib/api/enums";
import { formatDuration } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";

export interface SpanNode extends SpanResponse {
  children: SpanNode[];
}

export function buildTree(spans: SpanResponse[]): SpanNode[] {
  const map = new Map<string, SpanNode>();
  const roots: SpanNode[] = [];

  for (const span of spans) {
    map.set(span.span_id, { ...span, children: [] });
  }

  for (const node of map.values()) {
    if (node.parent_span_id && map.has(node.parent_span_id)) {
      map.get(node.parent_span_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

const SPAN_KIND_CONFIG: Record<
  string,
  { icon: typeof Bot; color: string; label: string }
> = {
  AGENT: { icon: Bot, color: "#3b82f6", label: "Agent" },
  TOOL: { icon: Wrench, color: "#eab308", label: "Tool" },
  LLM: { icon: Sparkles, color: "#a78bfa", label: "LLM" },
  RETRIEVER: { icon: Search, color: "#22c55e", label: "Retriever" },
  CHAIN: { icon: Link, color: "#6b7280", label: "Chain" },
  EMBEDDING: { icon: Grid3X3, color: "#06b6d4", label: "Embedding" },
  OTHER: { icon: Circle, color: "#4b5563", label: "Other" },
};

function getKindConfig(kind: SpanKind) {
  return SPAN_KIND_CONFIG[kind] ?? SPAN_KIND_CONFIG.OTHER;
}

function statusDotColor(status: string): string {
  if (status === SpanStatusCode.OK) return "bg-success";
  if (status === SpanStatusCode.ERROR) return "bg-error";
  return "bg-text-muted";
}

interface WaterfallTreeProps {
  trace: TraceResponse;
  tree: SpanNode[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function WaterfallTree({
  trace,
  tree,
  selectedId,
  onSelect,
}: WaterfallTreeProps) {
  return (
    <div className="py-1">
      <TraceRootNode
        trace={trace}
        selected={selectedId === "trace"}
        onSelect={() => onSelect("trace")}
      />
      {tree.map((node, i) => (
        <SpanWaterfallNode
          key={node.span_id}
          node={node}
          depth={0}
          selectedId={selectedId}
          onSelect={onSelect}
          isLast={i === tree.length - 1}
        />
      ))}
    </div>
  );
}

function TraceRootNode({
  trace,
  selected,
  onSelect,
}: {
  trace: TraceResponse;
  selected: boolean;
  onSelect: () => void;
}) {
  const latencyMs =
    trace.started_at && trace.ended_at
      ? new Date(trace.ended_at).getTime() -
        new Date(trace.started_at).getTime()
      : null;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full flex items-center gap-2 px-3 py-2 text-left transition-colors duration-100",
        "hover:bg-surface-hi",
        selected
          ? "bg-surface-hi border-l-2 border-l-primary"
          : "border-l-2 border-l-transparent",
      )}
    >
      <Activity className="h-3.5 w-3.5 text-primary flex-shrink-0" />
      <span className="text-xs font-mono text-text truncate flex-1">
        {trace.name}
      </span>
      <span className="text-[10px] font-mono text-text-muted uppercase tracking-wide flex-shrink-0">
        Trace
      </span>
      {latencyMs != null && (
        <span className="text-[10px] font-mono text-text-dim flex-shrink-0">
          {formatDuration(latencyMs)}
        </span>
      )}
    </button>
  );
}

const INDENT_PX = 20;

const SpanWaterfallNode = memo(function SpanWaterfallNode({
  node,
  depth,
  selectedId,
  onSelect,
  isLast,
}: {
  node: SpanNode;
  depth: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
  isLast: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children.length > 0;
  const kindCfg = getKindConfig(node.kind);
  const KindIcon = kindCfg.icon;
  const isSelected = selectedId === node.span_id;

  return (
    <div>
      <button
        type="button"
        onClick={() => onSelect(node.span_id)}
        className={cn(
          "w-full flex items-center gap-1.5 py-1.5 pr-3 text-left transition-colors duration-100",
          "hover:bg-surface-hi group",
          isSelected ? "bg-surface-hi" : "",
        )}
        style={{
          paddingLeft: `${(depth + 1) * INDENT_PX + 12}px`,
          borderLeft: isSelected
            ? `2px solid ${kindCfg.color}`
            : "2px solid transparent",
        }}
      >
        {/* Connector stub */}
        <div className="relative flex-shrink-0 w-4 h-4 flex items-center justify-center">
          {depth > 0 && (
            <div
              className="absolute border-l border-b border-border"
              style={{
                left: -10,
                top: -6,
                width: 10,
                height: isLast ? 14 : 14,
                borderBottomLeftRadius: 0,
              }}
            />
          )}
          {hasChildren ? (
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation();
                setExpanded((v) => !v);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  setExpanded((v) => !v);
                }
              }}
              className="relative z-10 text-text-muted hover:text-text transition-colors cursor-pointer"
            >
              {expanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </span>
          ) : (
            <div
              className="h-1 w-1 flex-shrink-0"
              style={{ backgroundColor: kindCfg.color, opacity: 0.5 }}
            />
          )}
        </div>

        <KindIcon
          className="h-3.5 w-3.5 flex-shrink-0"
          style={{ color: kindCfg.color }}
        />

        <span className="text-xs font-mono text-text truncate flex-1 min-w-0">
          {node.name}
        </span>

        <span
          className="text-[10px] font-mono uppercase tracking-wide flex-shrink-0 opacity-60"
          style={{ color: kindCfg.color }}
        >
          {kindCfg.label}
        </span>

        {node.model && (
          <span className="text-[10px] font-mono text-text-muted flex-shrink-0 max-w-[80px] truncate">
            {node.model}
          </span>
        )}

        <span className="text-[10px] font-mono text-text-dim flex-shrink-0">
          {formatDuration(node.latency_ms)}
        </span>

        <div
          className={cn(
            "h-1.5 w-1.5 flex-shrink-0",
            statusDotColor(node.status),
          )}
        />
      </button>

      {expanded &&
        hasChildren &&
        node.children.map((child, i) => (
          <SpanWaterfallNode
            key={child.span_id}
            node={child}
            depth={depth + 1}
            selectedId={selectedId}
            onSelect={onSelect}
            isLast={i === node.children.length - 1}
          />
        ))}
    </div>
  );
});

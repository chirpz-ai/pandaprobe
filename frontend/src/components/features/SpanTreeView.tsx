"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { SpanResponse } from "@/lib/api/types";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { formatDuration } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";

interface SpanNode extends SpanResponse {
  children: SpanNode[];
}

function buildTree(spans: SpanResponse[]): SpanNode[] {
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

function SpanNode({ node, depth }: { node: SpanNode; depth: number }) {
  const [expanded, setExpanded] = useState(true);
  const [showDetail, setShowDetail] = useState(false);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-1.5 hover:bg-surface-hi transition-colors cursor-pointer border-b border-border",
        )}
        style={{ paddingLeft: `${depth * 20 + 12}px` }}
        onClick={() => setShowDetail(!showDetail)}
      >
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
            className="text-text-muted hover:text-text"
          >
            {expanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
        ) : (
          <span className="w-3" />
        )}
        <Badge variant="default">{node.kind}</Badge>
        <span className="text-xs font-mono text-text truncate flex-1">
          {node.name}
        </span>
        <StatusBadge status={node.status} />
        <span className="text-xs text-text-dim ml-2">
          {formatDuration(node.latency_ms)}
        </span>
        {node.model && (
          <Badge variant="info">{node.model}</Badge>
        )}
      </div>

      {showDetail && (
        <div
          className="bg-surface-hi border-b border-border px-4 py-3 text-xs font-mono"
          style={{ paddingLeft: `${depth * 20 + 36}px` }}
        >
          <div className="grid grid-cols-2 gap-4 max-w-2xl">
            {node.input != null && (
              <div>
                <span className="text-text-muted block mb-1">Input</span>
                <pre className="text-text-dim overflow-auto max-h-40 bg-bg p-2 border border-border text-[10px]">
                  {typeof node.input === "string"
                    ? node.input
                    : JSON.stringify(node.input, null, 2)}
                </pre>
              </div>
            )}
            {node.output != null && (
              <div>
                <span className="text-text-muted block mb-1">Output</span>
                <pre className="text-text-dim overflow-auto max-h-40 bg-bg p-2 border border-border text-[10px]">
                  {typeof node.output === "string"
                    ? node.output
                    : JSON.stringify(node.output, null, 2)}
                </pre>
              </div>
            )}
          </div>
          {node.error && (
            <div className="mt-2">
              <span className="text-error block mb-1">Error</span>
              <pre className="text-error/80 overflow-auto max-h-20 bg-error/5 p-2 border border-error/20 text-[10px]">
                {node.error}
              </pre>
            </div>
          )}
          {node.token_usage && Object.keys(node.token_usage).length > 0 && (
            <div className="mt-2">
              <span className="text-text-muted block mb-1">Token Usage</span>
              <pre className="text-text-dim text-[10px]">
                {JSON.stringify(node.token_usage, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {expanded &&
        node.children.map((child) => (
          <SpanNode key={child.span_id} node={child} depth={depth + 1} />
        ))}
    </div>
  );
}

export function SpanTreeView({ spans }: { spans: SpanResponse[] }) {
  const tree = buildTree(spans);

  if (tree.length === 0) {
    return (
      <div className="text-xs text-text-muted py-4 text-center">
        No spans recorded
      </div>
    );
  }

  return (
    <div className="border border-border">
      {tree.map((node) => (
        <SpanNode key={node.span_id} node={node} depth={0} />
      ))}
    </div>
  );
}

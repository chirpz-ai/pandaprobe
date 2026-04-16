"use client";

import { useState, useMemo, useCallback } from "react";
import type { TraceResponse, SpanResponse } from "@/lib/api/types";
import { WaterfallTree, buildTree } from "./WaterfallTree";
import { SpanDetailPanel } from "./SpanDetailPanel";

interface SpanWaterfallProps {
  trace: TraceResponse;
}

export function SpanWaterfall({ trace }: SpanWaterfallProps) {
  const tree = useMemo(() => buildTree(trace.spans), [trace.spans]);
  const [selectedId, setSelectedId] = useState<string>("trace");

  const spanMap = useMemo(() => {
    const map = new Map<string, SpanResponse>();
    for (const span of trace.spans) {
      map.set(span.span_id, span);
    }
    return map;
  }, [trace.spans]);

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const selectedSpan = selectedId === "trace" ? null : (spanMap.get(selectedId) ?? null);
  const mode = selectedId === "trace" ? "trace" as const : "span" as const;

  if (trace.spans.length === 0) {
    return (
      <div className="text-xs text-text-muted font-mono py-4 text-center border border-border">
        No spans recorded
      </div>
    );
  }

  return (
    <div className="border border-border flex flex-col md:flex-row max-h-[calc(100vh-380px)]">
      {/* Left panel — waterfall tree */}
      <div className="md:w-[38%] w-full max-h-[50vh] md:max-h-none overflow-y-auto overflow-x-hidden border-b md:border-b-0 md:border-r border-border flex-shrink-0">
        <div className="sticky top-0 z-10 bg-surface px-3 py-1.5 border-b border-border">
          <span className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
            Spans · {trace.spans.length}
          </span>
        </div>
        <WaterfallTree
          trace={trace}
          tree={tree}
          selectedId={selectedId}
          onSelect={handleSelect}
        />
      </div>

      {/* Right panel — detail view */}
      <div className="flex-1 min-w-0 overflow-y-auto bg-surface">
        <SpanDetailPanel
          trace={trace}
          span={selectedSpan}
          mode={mode}
        />
      </div>
    </div>
  );
}

"use client";

import {
  useState,
  useMemo,
  useCallback,
  useEffect,
  type RefObject,
} from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import type { TraceResponse, SpanResponse } from "@/lib/api/types";
import { WaterfallTree, buildTree } from "./WaterfallTree";
import { SpanDetailPanel } from "./SpanDetailPanel";

interface SpanWaterfallProps {
  trace: TraceResponse;
  /** Element to expand over. Omit to hide the expand control. */
  overlayTargetRef?: RefObject<HTMLElement | null>;
}
const STACK_GAP_PX = 24;
const COLLAPSED_MAX_H = "calc(100vh - 380px)";

export function SpanWaterfall({ trace, overlayTargetRef }: SpanWaterfallProps) {
  const tree = useMemo(() => buildTree(trace.spans), [trace.spans]);
  const [selectedId, setSelectedId] = useState<string>("trace");
  const [expanded, setExpanded] = useState(false);
  const [overlap, setOverlap] = useState(0);

  const toggleExpanded = useCallback(() => {
    setExpanded((wasExpanded) => !wasExpanded);
    const target = overlayTargetRef?.current;
    setOverlap(target ? target.offsetHeight + STACK_GAP_PX : 0);
  }, [overlayTargetRef]);

  // The covered card reflows when tags wrap or the grid hits a breakpoint.
  useEffect(() => {
    const target = overlayTargetRef?.current;
    if (!expanded || !target || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() =>
      setOverlap(target.offsetHeight + STACK_GAP_PX),
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [expanded, overlayTargetRef]);

  useEffect(() => {
    if (!expanded) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expanded]);

  const canExpand = overlayTargetRef !== undefined;
  const isExpanded = expanded && canExpand;

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

  const selectedSpan =
    selectedId === "trace" ? null : (spanMap.get(selectedId) ?? null);
  const mode = selectedId === "trace" ? ("trace" as const) : ("span" as const);

  if (trace.spans.length === 0) {
    return (
      <div className="text-xs text-text-muted font-mono py-4 text-center border border-border">
        No spans recorded
      </div>
    );
  }

  return (
    <div
      className={cn(
        "relative border border-border flex flex-col md:flex-row",
        isExpanded && "z-30 bg-surface shadow-2xl",
      )}
      style={{
        marginTop: isExpanded ? -overlap : undefined,
        maxHeight: isExpanded
          ? `calc(${COLLAPSED_MAX_H} + ${overlap}px)`
          : COLLAPSED_MAX_H,
      }}
    >
      {/* Left panel — waterfall tree */}
      <div className="md:w-[38%] w-full max-h-[50vh] md:max-h-none overflow-y-auto overflow-x-hidden border-b md:border-b-0 md:border-r border-border flex-shrink-0 bg-surface">
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
        <SpanDetailPanel trace={trace} span={selectedSpan} mode={mode} />
      </div>

      {canExpand && (
        <button
          type="button"
          onClick={toggleExpanded}
          aria-expanded={isExpanded}
          title={
            isExpanded
              ? "Collapse (Esc)"
              : "Expand over the trace metadata for more room"
          }
          className="absolute top-2 right-2 z-20 inline-flex items-center justify-center h-6 w-6 border border-border bg-surface text-text-muted hover:text-text transition-colors"
        >
          {isExpanded ? (
            <Minimize2 className="h-3 w-3" />
          ) : (
            <Maximize2 className="h-3 w-3" />
          )}
          <span className="sr-only">
            {isExpanded ? "Collapse span panel" : "Expand span panel"}
          </span>
        </button>
      )}
    </div>
  );
}

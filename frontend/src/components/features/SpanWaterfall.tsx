"use client";

import { useState, useMemo, useCallback, useRef } from "react";
import { cn } from "@/lib/utils/cn";
import type { TraceResponse } from "@/lib/api/types";
import { buildTree } from "@/lib/utils/trace-timeline";
import { WaterfallTree } from "./WaterfallTree";
import { SpanDetailPanel } from "./SpanDetailPanel";

export function SpanWaterfall({ trace }: { trace: TraceResponse }) {
  const tree = useMemo(() => buildTree(trace.spans), [trace.spans]);
  const [selectedId, setSelectedId] = useState("trace");
  const detailRef = useRef<HTMLElement>(null);
  const [mobilePane, setMobilePane] = useState<"waterfall" | "details">(
    "waterfall",
  );
  const selectedSpan =
    trace.spans.find((span) => span.span_id === selectedId) ?? null;
  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
    setMobilePane("details");
    if (detailRef.current) detailRef.current.scrollTop = 0;
  }, []);

  return (
    <div className="flex flex-1 min-h-0 min-w-0 flex-col border border-border bg-surface">
      <div
        className="flex border-b border-border lg:hidden"
        aria-label="Trace panels"
      >
        {(["waterfall", "details"] as const).map((pane) => (
          <button
            key={pane}
            type="button"
            aria-pressed={mobilePane === pane}
            onClick={() => setMobilePane(pane)}
            className={cn(
              "flex-1 px-3 py-2.5 text-xs font-mono focus-visible:outline focus-visible:outline-primary",
              mobilePane === pane
                ? "bg-surface-hi text-primary"
                : "text-text-muted",
            )}
          >
            {pane === "waterfall"
              ? `Waterfall · ${trace.spans.length}`
              : "Span details"}
          </button>
        ))}
      </div>
      <div className="flex flex-1 min-h-0 min-w-0">
        <section
          aria-label="Trace waterfall"
          className={cn(
            "min-w-0 w-full lg:w-[48%] lg:shrink-0 lg:border-r border-border overflow-auto bg-surface",
            mobilePane !== "waterfall" && "hidden lg:block",
          )}
        >
          <WaterfallTree
            trace={trace}
            tree={tree}
            selectedId={selectedId}
            onSelect={handleSelect}
          />
        </section>
        <section
          aria-label="Selected span details"
          ref={detailRef}
          className={cn(
            "min-w-0 flex-1 overflow-auto bg-surface",
            mobilePane !== "details" && "hidden lg:block",
          )}
        >
          <SpanDetailPanel
            trace={trace}
            span={selectedSpan}
            mode={selectedSpan ? "span" : "trace"}
          />
        </section>
      </div>
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { ListTree, SquareChartGantt } from "lucide-react";
import type { TraceResponse } from "@/lib/api/types";
import { getTimeline, type SpanNode } from "@/lib/utils/trace-timeline";
import { WaterfallTree } from "./WaterfallTree";
import { Timeline, TimelineRuler } from "./Timeline";

interface WaterfallTabsProps {
  trace: TraceResponse;
  tree: SpanNode[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/** Owns the shared navigation state for the Waterfall and Timeline views. */
export function WaterfallTabs({
  trace,
  tree,
  selectedId,
  onSelect,
}: WaterfallTabsProps) {
  const timeline = useMemo(() => getTimeline(trace), [trace]);
  const [view, setView] = useState("timeline");
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const toggle = (id: string) =>
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const sharedProps = {
    trace,
    tree,
    collapsed,
    selectedId,
    onSelect,
    onToggle: toggle,
  };

  return (
    <Tabs.Root
      value={view}
      onValueChange={setView}
      className="min-w-0 min-h-full"
    >
      <div className="sticky top-0 z-20 bg-surface border-b border-border">
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-3">
          <span className="text-[10px] font-mono uppercase tracking-wider text-text-muted">
            Spans · {trace.spans.length}
          </span>
          <Tabs.List
            aria-label="Waterfall view"
            className="flex border border-border p-0.5"
          >
            <Tabs.Trigger
              value="waterfall"
              className="flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono text-text-muted data-[state=active]:bg-surface-hi data-[state=active]:text-primary focus-visible:outline focus-visible:outline-primary"
            >
              <ListTree aria-hidden="true" className="h-3.5 w-3.5" />
              Waterfall
            </Tabs.Trigger>
            <Tabs.Trigger
              value="timeline"
              className="flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono text-text-muted data-[state=active]:bg-surface-hi data-[state=active]:text-primary focus-visible:outline focus-visible:outline-primary"
            >
              <SquareChartGantt aria-hidden="true" className="h-3.5 w-3.5" />
              Timeline
            </Tabs.Trigger>
          </Tabs.List>
        </div>
        {view === "timeline" && <TimelineRuler timeline={timeline} />}
      </div>
      <Tabs.Content value="waterfall" className="focus-visible:outline-none">
        <WaterfallTree {...sharedProps} />
      </Tabs.Content>
      <Tabs.Content value="timeline" className="focus-visible:outline-none">
        <Timeline {...sharedProps} timeline={timeline} />
      </Tabs.Content>
      {trace.spans.length === 0 && (
        <p className="p-6 text-center text-xs font-mono text-text-muted">
          No spans recorded
        </p>
      )}
    </Tabs.Root>
  );
}

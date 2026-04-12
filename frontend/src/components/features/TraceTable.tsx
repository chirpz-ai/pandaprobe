"use client";

import { useCallback } from "react";
import Link from "next/link";
import type { TraceListItem } from "@/lib/api/types";
import { StatusBadge } from "@/components/common/StatusBadge";
import {
  formatRelativeTime,
  formatDuration,
  formatCost,
} from "@/lib/utils/format";
import { Badge } from "@/components/ui/Badge";
import { useProjectPath } from "@/hooks/useNavigation";

interface TraceTableProps {
  traces: TraceListItem[];
  selected?: Set<string>;
  onSelectionChange?: (selected: Set<string>) => void;
}

export function TraceTable({
  traces,
  selected,
  onSelectionChange,
}: TraceTableProps) {
  const basePath = useProjectPath("/traces");
  const selectable = !!selected && !!onSelectionChange;

  const allSelected =
    selectable && traces.length > 0 && traces.every((t) => selected.has(t.trace_id));
  const someSelected =
    selectable && !allSelected && traces.some((t) => selected.has(t.trace_id));

  const toggleAll = useCallback(() => {
    if (!onSelectionChange) return;
    if (allSelected) {
      const next = new Set(selected);
      traces.forEach((t) => next.delete(t.trace_id));
      onSelectionChange(next);
    } else {
      const next = new Set(selected);
      traces.forEach((t) => next.add(t.trace_id));
      onSelectionChange(next);
    }
  }, [allSelected, onSelectionChange, selected, traces]);

  const toggleOne = useCallback(
    (id: string) => {
      if (!onSelectionChange || !selected) return;
      const next = new Set(selected);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      onSelectionChange(next);
    },
    [onSelectionChange, selected],
  );

  return (
    <div className="border border-border overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="border-b border-border bg-surface-hi">
            {selectable && (
              <th className="w-8 px-3 py-2">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = !!someSelected;
                  }}
                  onChange={toggleAll}
                />
              </th>
            )}
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Name
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Status
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Latency
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Tokens
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Cost
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Spans
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Started
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Tags
            </th>
          </tr>
        </thead>
        <tbody>
          {traces.map((trace) => (
            <tr
              key={trace.trace_id}
              className="border-b border-border hover:bg-surface-hi transition-colors"
            >
              {selectable && (
                <td className="w-8 px-3 py-2">
                  <input
                    type="checkbox"
                    checked={selected.has(trace.trace_id)}
                    onChange={() => toggleOne(trace.trace_id)}
                  />
                </td>
              )}
              <td className="px-3 py-2 max-w-[200px] truncate">
                <Link
                  href={`${basePath}/${trace.trace_id}`}
                  className="text-text hover:text-primary transition-colors"
                >
                  {trace.name}
                </Link>
              </td>
              <td className="px-3 py-2">
                <StatusBadge status={trace.status} />
              </td>
              <td className="px-3 py-2 text-text-dim">
                {formatDuration(trace.latency_ms)}
              </td>
              <td className="px-3 py-2 text-text-dim">{trace.total_tokens}</td>
              <td className="px-3 py-2 text-text-dim">
                {formatCost(trace.total_cost)}
              </td>
              <td className="px-3 py-2 text-text-dim">{trace.span_count}</td>
              <td className="px-3 py-2 text-text-dim">
                {formatRelativeTime(trace.started_at)}
              </td>
              <td className="px-3 py-2">
                <div className="flex gap-1 flex-wrap">
                  {trace.tags.slice(0, 3).map((tag) => (
                    <Badge key={tag} variant="default">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

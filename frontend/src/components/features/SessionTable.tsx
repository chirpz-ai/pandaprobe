"use client";

import { useCallback, useRef } from "react";
import Link from "next/link";
import type { SessionSummary } from "@/lib/api/types";
import { Badge } from "@/components/ui/Badge";
import {
  formatRelativeTime,
  formatDuration,
  // TODO(cost): re-enable when session cost computation is implemented.
  // formatCost,
} from "@/lib/utils/format";
import { useProjectPath } from "@/hooks/useNavigation";
import { cn } from "@/lib/utils/cn";

interface SessionTableProps {
  sessions: SessionSummary[];
  selected?: Set<string>;
  onSelectionChange?: (selected: Set<string>) => void;
  lastVisited?: string | null;
  onRowVisit?: (id: string) => void;
}

export function SessionTable({
  sessions,
  selected,
  onSelectionChange,
  lastVisited,
  onRowVisit,
}: SessionTableProps) {
  const basePath = useProjectPath("/sessions");
  const selectable = !!selected && !!onSelectionChange;
  const hasScrolled = useRef(false);
  const scrollToRef = useCallback((node: HTMLTableRowElement | null) => {
    if (node && !hasScrolled.current) {
      hasScrolled.current = true;
      requestAnimationFrame(() => {
        node.scrollIntoView({ block: "center", behavior: "smooth" });
      });
    }
  }, []);

  const allSelected =
    selectable &&
    sessions.length > 0 &&
    sessions.every((s) => selected.has(s.session_id));
  const someSelected =
    selectable &&
    !allSelected &&
    sessions.some((s) => selected.has(s.session_id));

  const toggleAll = useCallback(() => {
    if (!onSelectionChange || !selected) return;
    if (allSelected) {
      const next = new Set(selected);
      sessions.forEach((s) => next.delete(s.session_id));
      onSelectionChange(next);
    } else {
      const next = new Set(selected);
      sessions.forEach((s) => next.add(s.session_id));
      onSelectionChange(next);
    }
  }, [allSelected, onSelectionChange, selected, sessions]);

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
    <div className="border border-border">
      <table className="w-full text-xs font-mono">
        <thead className="sticky top-0 z-10 bg-surface-hi">
          <tr className="border-b border-border">
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
              Session ID
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Traces
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Error
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Latency
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Tokens
            </th>
            {/* TODO(cost): Restore Cost column once session cost computation is implemented. */}
            {/* <th className="text-left px-3 py-2 text-text-muted font-normal">
              Cost
            </th> */}
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              First Trace
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Tags
            </th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((session) => (
            <tr
              key={session.session_id}
              ref={
                lastVisited === session.session_id
                  ? scrollToRef
                  : undefined
              }
              className={cn(
                "border-b border-border border-l-2 hover:bg-surface-hi transition-colors",
                lastVisited === session.session_id
                  ? "border-l-primary/40 bg-primary/[0.03]"
                  : "border-l-transparent",
              )}
            >
              {selectable && (
                <td className="w-8 px-3 py-2">
                  <input
                    type="checkbox"
                    checked={selected.has(session.session_id)}
                    onChange={() => toggleOne(session.session_id)}
                  />
                </td>
              )}
              <td className="px-3 py-2 max-w-[200px] truncate">
                <Link
                  href={`${basePath}/${session.session_id}`}
                  onClick={() => onRowVisit?.(session.session_id)}
                  className="text-text hover:text-primary transition-colors"
                >
                  {session.session_id}
                </Link>
              </td>
              <td className="px-3 py-2 text-text-dim">{session.trace_count}</td>
              <td className="px-3 py-2">
                {session.has_error ? (
                  <Badge variant="error">Error</Badge>
                ) : (
                  <Badge variant="success">OK</Badge>
                )}
              </td>
              <td className="px-3 py-2 text-text-dim">
                {formatDuration(session.total_latency_ms)}
              </td>
              <td className="px-3 py-2 text-text-dim">
                {session.total_tokens}
              </td>
              {/* TODO(cost): Restore Cost cell once session cost computation is implemented. */}
              {/* <td className="px-3 py-2 text-text-dim">
                {formatCost(session.total_cost)}
              </td> */}
              <td className="px-3 py-2 text-text-dim">
                {formatRelativeTime(session.first_trace_at)}
              </td>
              <td className="px-3 py-2">
                <div className="flex gap-1 flex-wrap">
                  {session.tags.slice(0, 3).map((tag) => (
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

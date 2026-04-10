"use client";

import Link from "next/link";
import type { TraceListItem } from "@/lib/api/types";
import { StatusBadge } from "@/components/common/StatusBadge";
import { formatRelativeTime, formatDuration, formatCost } from "@/lib/utils/format";
import { Badge } from "@/components/ui/Badge";
import { useProjectPath } from "@/hooks/useNavigation";

interface TraceTableProps {
  traces: TraceListItem[];
}

export function TraceTable({ traces }: TraceTableProps) {
  const basePath = useProjectPath("/traces");
  return (
    <div className="border border-border overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="border-b border-border bg-surface-hi">
            <th className="text-left px-3 py-2 text-text-muted font-normal">Name</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Status</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Latency</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Tokens</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Cost</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Spans</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Started</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Tags</th>
          </tr>
        </thead>
        <tbody>
          {traces.map((trace) => (
            <tr
              key={trace.trace_id}
              className="border-b border-border hover:bg-surface-hi transition-colors"
            >
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

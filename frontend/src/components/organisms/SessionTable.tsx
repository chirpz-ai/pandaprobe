"use client";

import Link from "next/link";
import type { SessionSummary } from "@/lib/api/types";
import { Badge } from "@/components/atoms/Badge";
import { formatRelativeTime, formatDuration, formatCost } from "@/lib/utils/format";

interface SessionTableProps {
  sessions: SessionSummary[];
}

export function SessionTable({ sessions }: SessionTableProps) {
  return (
    <div className="border border-border overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="border-b border-border bg-surface-hi">
            <th className="text-left px-3 py-2 text-text-muted font-normal">Session ID</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Traces</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Error</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Latency</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Tokens</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Cost</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">First Trace</th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">Tags</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((session) => (
            <tr
              key={session.session_id}
              className="border-b border-border hover:bg-surface-hi transition-colors"
            >
              <td className="px-3 py-2 max-w-[200px] truncate">
                <Link
                  href={`/dashboard/sessions/${session.session_id}`}
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
              <td className="px-3 py-2 text-text-dim">{session.total_tokens}</td>
              <td className="px-3 py-2 text-text-dim">
                {formatCost(session.total_cost)}
              </td>
              <td className="px-3 py-2 text-text-dim">
                {formatRelativeTime(session.first_trace_at)}
              </td>
              <td className="px-3 py-2">
                <div className="flex gap-1 flex-wrap">
                  {session.tags.slice(0, 3).map((tag) => (
                    <Badge key={tag} variant="default">{tag}</Badge>
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

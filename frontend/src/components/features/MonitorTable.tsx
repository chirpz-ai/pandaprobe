"use client";

import type { MonitorResponse } from "@/lib/api/types";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { formatRelativeTime } from "@/lib/utils/format";

interface MonitorTableProps {
  monitors: MonitorResponse[];
  onSelect?: (monitor: MonitorResponse) => void;
}

export function MonitorTable({ monitors, onSelect }: MonitorTableProps) {
  return (
    <div className="border border-border">
      <table className="w-full text-xs font-mono">
        <thead className="sticky top-0 z-10 bg-surface-hi">
          <tr className="border-b border-border">
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Name / ID
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Status
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Target
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Cadence
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Metrics
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Sampling
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Last run
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Next run
            </th>
          </tr>
        </thead>
        <tbody>
          {monitors.map((m) => (
            <tr
              key={m.id}
              className="border-b border-border hover:bg-surface-hi transition-colors cursor-pointer"
              onClick={() => onSelect?.(m)}
            >
              <td className="px-3 py-2 max-w-[220px] truncate text-text">
                {m.name || m.id.slice(0, 8)}
                <span
                  className="ml-2 text-[10px] text-text-muted"
                  title={m.id}
                >
                  {m.id.slice(0, 8)}
                </span>
              </td>
              <td className="px-3 py-2">
                <StatusBadge status={m.status} />
              </td>
              <td className="px-3 py-2 text-text-dim">{m.target_type}</td>
              <td
                className="px-3 py-2 text-text-dim max-w-[180px] truncate"
                title={m.cadence}
              >
                {formatCadence(m.cadence)}
              </td>
              <td className="px-3 py-2">
                <div className="flex gap-1 flex-wrap">
                  {m.metric_names.slice(0, 3).map((name) => (
                    <Badge key={name} variant="info">
                      {name}
                    </Badge>
                  ))}
                  {m.metric_names.length > 3 && (
                    <span className="text-[10px] text-text-muted self-center">
                      +{m.metric_names.length - 3}
                    </span>
                  )}
                </div>
              </td>
              <td className="px-3 py-2 text-text-dim">
                {formatSamplingRate(m.sampling_rate)}
              </td>
              <td className="px-3 py-2 text-text-dim">
                {m.last_run_at ? (
                  formatRelativeTime(m.last_run_at)
                ) : (
                  <span className="text-text-muted">—</span>
                )}
              </td>
              <td className="px-3 py-2 text-text-dim">
                {m.next_run_at ? (
                  formatRelativeTime(m.next_run_at)
                ) : (
                  <span className="text-text-muted">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatSamplingRate(rate: number): string {
  if (rate == null || Number.isNaN(rate)) return "—";
  if (rate >= 1) return "100%";
  return `${Math.round(rate * 100)}%`;
}

function formatCadence(cadence: string): string {
  if (!cadence) return "—";
  if (cadence.startsWith("cron:")) {
    return `cron: ${cadence.slice("cron:".length).trim()}`;
  }
  switch (cadence) {
    case "every_6h":
      return "every 6h";
    case "daily":
      return "daily";
    case "weekly":
      return "weekly";
    default:
      return cadence;
  }
}

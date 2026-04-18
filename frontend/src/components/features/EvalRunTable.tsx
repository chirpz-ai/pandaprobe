"use client";

import type { EvalRunResponse } from "@/lib/api/types";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { formatRelativeTime } from "@/lib/utils/format";

interface EvalRunTableProps {
  runs: EvalRunResponse[];
  onSelect?: (run: EvalRunResponse) => void;
}

export function EvalRunTable({ runs, onSelect }: EvalRunTableProps) {
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
              Metrics
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Progress
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Target
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Sampling
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Model
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Created
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Completed
            </th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr
              key={run.id}
              className="border-b border-border hover:bg-surface-hi transition-colors cursor-pointer"
              onClick={() => onSelect?.(run)}
            >
              <td className="px-3 py-2 max-w-[220px] truncate text-text">
                {run.name || run.id.slice(0, 8)}
                {run.monitor_id && (
                  <span className="ml-2 text-[10px] text-text-muted">
                    · monitor
                  </span>
                )}
              </td>
              <td className="px-3 py-2">
                <StatusBadge status={run.status} />
              </td>
              <td className="px-3 py-2">
                <div className="flex gap-1 flex-wrap">
                  {run.metric_names.slice(0, 3).map((m) => (
                    <Badge key={m} variant="info">
                      {m}
                    </Badge>
                  ))}
                  {run.metric_names.length > 3 && (
                    <span className="text-[10px] text-text-muted self-center">
                      +{run.metric_names.length - 3}
                    </span>
                  )}
                </div>
              </td>
              <td className="px-3 py-2 text-text-dim">
                {run.evaluated_count}/{run.total_targets}
                {run.failed_count > 0 && (
                  <span className="text-error ml-1">
                    ({run.failed_count} failed)
                  </span>
                )}
              </td>
              <td className="px-3 py-2 text-text-dim">{run.target_type}</td>
              <td className="px-3 py-2 text-text-dim">
                {formatSamplingRate(run.sampling_rate)}
              </td>
              <td className="px-3 py-2 text-text-dim max-w-[160px] truncate">
                {run.model ?? (
                  <span className="text-text-muted">default</span>
                )}
              </td>
              <td className="px-3 py-2 text-text-dim">
                {formatRelativeTime(run.created_at)}
              </td>
              <td className="px-3 py-2 text-text-dim">
                {run.completed_at ? (
                  formatRelativeTime(run.completed_at)
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

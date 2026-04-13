"use client";

import type { MonitorResponse } from "@/lib/api/types";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatRelativeTime } from "@/lib/utils/format";
import { Pause, Play, Zap, Trash2 } from "lucide-react";

interface MonitorCardProps {
  monitor: MonitorResponse;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  onTrigger: (id: string) => void;
  onDelete: (id: string) => void;
}

export function MonitorCard({
  monitor,
  onPause,
  onResume,
  onTrigger,
  onDelete,
}: MonitorCardProps) {
  const isActive = monitor.status === "ACTIVE";

  return (
    <div className="border-engraved bg-surface p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-mono text-text">{monitor.name}</h3>
          <span className="text-[10px] text-text-muted font-mono">
            {monitor.id.slice(0, 8)}
          </span>
        </div>
        <StatusBadge status={monitor.status} />
      </div>

      <div className="flex flex-wrap gap-1">
        {monitor.metric_names.map((m) => (
          <Badge key={m} variant="info">
            {m}
          </Badge>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
        <div>
          <span className="text-text-muted block">Target</span>
          <span className="text-text">{monitor.target_type}</span>
        </div>
        <div>
          <span className="text-text-muted block">Cadence</span>
          <span className="text-text">{monitor.cadence}</span>
        </div>
        <div>
          <span className="text-text-muted block">Last Run</span>
          <span className="text-text">
            {formatRelativeTime(monitor.last_run_at)}
          </span>
        </div>
        <div>
          <span className="text-text-muted block">Next Run</span>
          <span className="text-text">
            {formatRelativeTime(monitor.next_run_at)}
          </span>
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        {isActive ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onPause(monitor.id)}
          >
            <Pause className="h-3 w-3" /> Pause
          </Button>
        ) : (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onResume(monitor.id)}
          >
            <Play className="h-3 w-3" /> Resume
          </Button>
        )}
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onTrigger(monitor.id)}
        >
          <Zap className="h-3 w-3" /> Trigger
        </Button>
        <Button
          variant="destructive"
          size="sm"
          onClick={() => onDelete(monitor.id)}
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

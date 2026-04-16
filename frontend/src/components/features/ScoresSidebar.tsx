"use client";

import { X } from "lucide-react";
import type { TraceScoreResponse } from "@/lib/api/types";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatDateTime } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";

interface ScoresSidebarProps {
  scores: TraceScoreResponse[];
  open: boolean;
  onClose: () => void;
}

export function ScoresSidebar({ scores, open, onClose }: ScoresSidebarProps) {
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-bg/50"
          onClick={onClose}
        />
      )}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-[380px] max-w-[90vw] bg-surface border-l border-border",
          "flex flex-col transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border flex-shrink-0">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider">
            Scores · {scores.length}
          </h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          {scores.length === 0 ? (
            <div className="flex items-center justify-center h-full text-xs text-text-muted font-mono">
              No scores available
            </div>
          ) : (
            <div className="divide-y divide-border">
              {scores.map((score) => (
                <ScoreRow key={score.id} score={score} />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function ScoreRow({ score }: { score: TraceScoreResponse }) {
  return (
    <div className="px-4 py-3 hover:bg-surface-hi transition-colors">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-mono text-text font-medium">
          {score.name}
        </span>
        <StatusBadge status={score.status} />
      </div>

      <div className="flex items-baseline gap-3 mb-2">
        <span className="text-lg font-mono text-primary">
          {score.value ?? "—"}
        </span>
        <Badge variant="default">{score.data_type}</Badge>
        <Badge variant="default">{score.source}</Badge>
      </div>

      {score.reason && (
        <p className="text-xs font-mono text-text-dim mb-2 whitespace-pre-wrap">
          {score.reason}
        </p>
      )}

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] font-mono text-text-muted">
        <span>Created {formatDateTime(score.created_at)}</span>
        <span>Updated {formatDateTime(score.updated_at)}</span>
        {score.eval_run_id && (
          <span className="truncate col-span-2">
            Eval run: {score.eval_run_id}
          </span>
        )}
      </div>
    </div>
  );
}

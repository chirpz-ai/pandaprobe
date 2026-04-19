"use client";

import { X, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils/cn";
import { ScoreRow, type ScoreItem } from "@/components/common/ScoreRow";

interface ScoresSidebarProps {
  scores: ScoreItem[];
  open: boolean;
  onClose: () => void;
  onScoreUpdated?: () => void;
  onScoreDeleted?: () => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function ScoresSidebar({
  scores,
  open,
  onClose,
  onScoreUpdated,
  onScoreDeleted,
  onRefresh,
  isRefreshing = false,
}: ScoresSidebarProps) {
  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-bg/50" onClick={onClose} />
      )}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-[500px] max-w-[90vw] bg-surface border-l border-border",
          "flex flex-col transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between h-12 px-4 border-b border-border flex-shrink-0">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider">
            Scores · {scores.length}
          </h2>
          <div className="flex items-center gap-1">
            {onRefresh && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onRefresh}
                disabled={isRefreshing}
                aria-label="Refresh scores"
                title="Refresh scores"
              >
                <RefreshCw
                  className={cn("h-3.5 w-3.5", isRefreshing && "animate-spin")}
                />
              </Button>
            )}
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          {scores.length === 0 ? (
            <div className="flex items-center justify-center h-full text-xs text-text-muted font-mono">
              No scores available
            </div>
          ) : (
            <div className="divide-y divide-border">
              {scores.map((score) => (
                <ScoreRow
                  key={score.id}
                  score={score}
                  onScoreUpdated={onScoreUpdated}
                  onScoreDeleted={onScoreDeleted}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

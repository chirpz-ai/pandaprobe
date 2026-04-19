"use client";

import { useState, type ComponentType } from "react";
import {
  ChevronDown,
  ChevronRight,
  ListTree,
  Layers,
  Copy,
  Check,
  MessageSquareText,
  FlaskConical,
  User,
  Settings,
  RefreshCw,
} from "lucide-react";
import type { TraceScoreResponse, SessionScoreResponse } from "@/lib/api/types";
import { ScoreSource } from "@/lib/api/enums";
import { StatusBadge } from "@/components/common/StatusBadge";
import { MetadataSection } from "@/components/common/ScoreRow";
import { Badge } from "@/components/ui/Badge";
import { Tooltip } from "@/components/ui/Tooltip";
import { formatDateTime, formatRelativeTime } from "@/lib/utils/format";

type ScoreItem = TraceScoreResponse | SessionScoreResponse;
type SourceVariant =
  | "default"
  | "success"
  | "warning"
  | "error"
  | "info"
  | "primary";

interface ScoreListTableProps {
  mode: "trace" | "session";
  scores: ScoreItem[];
  /** Called when the user clicks the Run cell; opens a run detail sidebar. */
  onOpenRun?: (runId: string) => void;
  /** Called when the user clicks the Target (trace/session) cell. */
  onNavigateTarget?: (targetId: string) => void;
}

/**
 * Project-wide score browser table. Each row collapses high-level info
 * (metric / value / status / source / env / target / run / created) and
 * expands inline to show reasoning, metadata, and secondary fields. The
 * target and run cells are themselves clickable — target navigates to
 * the source trace/session page, run opens the evaluation run sidebar
 * in-place without leaving the filter context.
 */
export function ScoreListTable({
  mode,
  scores,
  onOpenRun,
  onNavigateTarget,
}: ScoreListTableProps) {
  const TargetIcon = mode === "trace" ? ListTree : Layers;
  const targetLabel = mode === "trace" ? "Trace" : "Session";
  const colCount = mode === "trace" ? 9 : 8;

  return (
    <div className="border border-border">
      <table className="w-full text-xs font-mono">
        <thead className="sticky top-0 z-10 bg-surface-hi">
          <tr className="border-b border-border">
            <th className="w-8" aria-label="Expand" />
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Metric
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Value
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Status
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Source
            </th>
            {mode === "trace" && (
              <th className="text-left px-3 py-2 text-text-muted font-normal">
                Env
              </th>
            )}
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              {targetLabel}
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Run
            </th>
            <th className="text-left px-3 py-2 text-text-muted font-normal">
              Created
            </th>
          </tr>
        </thead>
        <tbody>
          {scores.map((score) => (
            <ScoreListRow
              key={score.id}
              score={score}
              mode={mode}
              TargetIcon={TargetIcon}
              targetLabel={targetLabel}
              colCount={colCount}
              onOpenRun={onOpenRun}
              onNavigateTarget={onNavigateTarget}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScoreListRow({
  score,
  mode,
  TargetIcon,
  targetLabel,
  colCount,
  onOpenRun,
  onNavigateTarget,
}: {
  score: ScoreItem;
  mode: "trace" | "session";
  TargetIcon: ComponentType<{ className?: string }>;
  targetLabel: string;
  colCount: number;
  onOpenRun?: (runId: string) => void;
  onNavigateTarget?: (targetId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copiedTarget, setCopiedTarget] = useState(false);
  const [copiedRun, setCopiedRun] = useState(false);
  const [copiedScoreId, setCopiedScoreId] = useState(false);

  const traceScore = "trace_id" in score ? (score as TraceScoreResponse) : null;
  const targetId = scoreTargetId(score);
  const runId = score.eval_run_id;

  function toggle() {
    setExpanded((v) => !v);
  }

  function handleCopyTarget(e: React.MouseEvent) {
    e.stopPropagation();
    navigator.clipboard.writeText(targetId);
    setCopiedTarget(true);
    setTimeout(() => setCopiedTarget(false), 2000);
  }

  function handleNavigateTarget(e: React.MouseEvent) {
    e.stopPropagation();
    onNavigateTarget?.(targetId);
  }

  function handleCopyRun(e: React.MouseEvent) {
    e.stopPropagation();
    if (!runId) return;
    navigator.clipboard.writeText(runId);
    setCopiedRun(true);
    setTimeout(() => setCopiedRun(false), 2000);
  }

  function handleOpenRun(e: React.MouseEvent) {
    e.stopPropagation();
    if (!runId) return;
    onOpenRun?.(runId);
  }

  function handleCopyScoreId(e: React.MouseEvent) {
    e.stopPropagation();
    navigator.clipboard.writeText(score.id);
    setCopiedScoreId(true);
    setTimeout(() => setCopiedScoreId(false), 2000);
  }

  return (
    <>
      <tr
        className="border-b border-border hover:bg-surface-hi transition-colors cursor-pointer"
        onClick={toggle}
      >
        <td className="px-2 py-2 w-8 align-middle">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              toggle();
            }}
            aria-label={expanded ? "Collapse row" : "Expand row"}
            className="text-text-muted hover:text-text flex items-center justify-center"
          >
            {expanded ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>
        </td>
        <td className="px-3 py-2 max-w-[200px] truncate text-warning font-medium">
          {score.name}
        </td>
        <td className="px-3 py-2 max-w-[160px] truncate text-text">
          {score.value ?? <span className="text-text-muted">—</span>}
        </td>
        <td className="px-3 py-2">
          <StatusBadge status={score.status} />
        </td>
        <td className="px-3 py-2">
          <Badge variant={sourceVariant(score.source)}>{score.source}</Badge>
        </td>
        {mode === "trace" && (
          <td className="px-3 py-2 max-w-[140px] truncate text-text-dim">
            {traceScore?.environment ?? (
              <span className="text-text-muted">—</span>
            )}
          </td>
        )}
        <td
          className="px-3 py-2 max-w-[200px]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center gap-1.5 min-w-0 group/cell">
            <TargetIcon className="h-3 w-3 text-text-muted flex-shrink-0" />
            <button
              type="button"
              onClick={handleNavigateTarget}
              className="truncate text-text-dim hover:text-text hover:underline underline-offset-2 min-w-0 text-left"
              title={`Open ${mode === "trace" ? "trace" : "session"}: ${targetId}`}
            >
              {targetId}
            </button>
            <Tooltip
              content={
                copiedTarget
                  ? "Copied!"
                  : `Copy ${targetLabel.toLowerCase()} ID`
              }
            >
              <button
                type="button"
                onClick={handleCopyTarget}
                className="text-text-muted hover:text-text transition-opacity opacity-0 group-hover/cell:opacity-100 focus:opacity-100 flex-shrink-0"
                aria-label={`Copy ${targetLabel.toLowerCase()} ID`}
              >
                {copiedTarget ? (
                  <Check className="h-3 w-3 text-success" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </button>
            </Tooltip>
          </div>
        </td>
        <td
          className="px-3 py-2 max-w-[200px]"
          onClick={(e) => e.stopPropagation()}
        >
          {runId ? (
            <div className="flex items-center gap-1.5 min-w-0 group/cell">
              <FlaskConical className="h-3 w-3 text-text-muted flex-shrink-0" />
              <button
                type="button"
                onClick={handleOpenRun}
                className="truncate text-text-dim hover:text-text hover:underline underline-offset-2 min-w-0 text-left"
                title={`Open evaluation run: ${runId}`}
              >
                {runId}
              </button>
              <Tooltip content={copiedRun ? "Copied!" : "Copy run ID"}>
                <button
                  type="button"
                  onClick={handleCopyRun}
                  className="text-text-muted hover:text-text transition-opacity opacity-0 group-hover/cell:opacity-100 focus:opacity-100 flex-shrink-0"
                  aria-label="Copy run ID"
                >
                  {copiedRun ? (
                    <Check className="h-3 w-3 text-success" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </button>
              </Tooltip>
            </div>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </td>
        <td className="px-3 py-2 text-text-dim whitespace-nowrap">
          <Tooltip content={formatDateTime(score.created_at)}>
            <span>{formatRelativeTime(score.created_at)}</span>
          </Tooltip>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border bg-surface-hi/30">
          <td colSpan={colCount} className="px-4 py-3">
            <ExpandedRowDetails
              score={score}
              copiedScoreId={copiedScoreId}
              onCopyScoreId={handleCopyScoreId}
            />
          </td>
        </tr>
      )}
    </>
  );
}

function ExpandedRowDetails({
  score,
  copiedScoreId,
  onCopyScoreId,
}: {
  score: ScoreItem;
  copiedScoreId: boolean;
  onCopyScoreId: (e: React.MouseEvent) => void;
}) {
  const traceScore = "trace_id" in score ? (score as TraceScoreResponse) : null;
  const hasMetadata = score.metadata && Object.keys(score.metadata).length > 0;

  return (
    <div className="space-y-3 max-w-full">
      {score.reason && (
        <div className="flex items-start gap-2">
          <MessageSquareText className="h-3 w-3 text-text-muted mt-0.5 flex-shrink-0" />
          <div className="min-w-0">
            <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider mb-0.5">
              Reasoning
            </div>
            <p className="text-xs font-mono text-text-dim whitespace-pre-wrap break-words">
              {score.reason}
            </p>
          </div>
        </div>
      )}

      {hasMetadata && (
        <MetadataSection data={score.metadata as Record<string, unknown>} />
      )}

      <div className="grid grid-cols-2 gap-3 text-[11px] font-mono">
        <DetailRow label="Data type">
          <Badge variant="default" className="text-[10px]">
            {score.data_type}
          </Badge>
        </DetailRow>
        {score.author_user_id && (
          <DetailRow label="Author">
            <span className="inline-flex items-center gap-1 text-text-dim min-w-0">
              <User className="h-2.5 w-2.5 flex-shrink-0" />
              <span className="truncate">{score.author_user_id}</span>
            </span>
          </DetailRow>
        )}
        {traceScore?.config_id && (
          <DetailRow label="Config">
            <span className="inline-flex items-center gap-1 text-text-dim min-w-0">
              <Settings className="h-2.5 w-2.5 flex-shrink-0" />
              <span className="truncate">{traceScore.config_id}</span>
            </span>
          </DetailRow>
        )}
        <DetailRow label="Score ID">
          <span className="inline-flex items-center gap-1 text-text-dim min-w-0 w-full">
            <span className="truncate" title={score.id}>
              {score.id}
            </span>
            <Tooltip content={copiedScoreId ? "Copied!" : "Copy score ID"}>
              <button
                type="button"
                onClick={onCopyScoreId}
                className="text-text-muted hover:text-text flex-shrink-0"
                aria-label="Copy score ID"
              >
                {copiedScoreId ? (
                  <Check className="h-3 w-3 text-success" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </button>
            </Tooltip>
          </span>
        </DetailRow>
        <DetailRow label="Updated">
          <span className="inline-flex items-center gap-1 text-text-dim">
            <RefreshCw className="h-2.5 w-2.5" />
            {formatDateTime(score.updated_at)}
          </span>
        </DetailRow>
      </div>
    </div>
  );
}

function DetailRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-wider text-text-muted">
        {label}
      </div>
      <div className="mt-0.5 min-w-0">{children}</div>
    </div>
  );
}

function scoreTargetId(score: ScoreItem): string {
  return "trace_id" in score ? score.trace_id : score.session_id;
}

function sourceVariant(source: string): SourceVariant {
  switch (source) {
    case ScoreSource.AUTOMATED:
      return "primary";
    case ScoreSource.ANNOTATION:
      return "info";
    case ScoreSource.PROGRAMMATIC:
      return "warning";
    default:
      return "default";
  }
}

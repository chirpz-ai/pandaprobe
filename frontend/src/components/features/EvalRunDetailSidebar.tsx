"use client";

import { useEffect, useMemo, useState } from "react";
import {
  useQuery,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import {
  X,
  RefreshCw,
  RotateCw,
  Trash2,
  Loader2,
  Clock,
  Filter,
  Radio,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import {
  getTraceRun,
  getSessionRun,
  getTraceRunScores,
  getSessionRunScores,
  retryTraceRun,
  retrySessionRun,
  deleteTraceRun,
  deleteSessionRun,
} from "@/lib/api/evaluations";
import type {
  EvalRunResponse,
  TraceScoreResponse,
  SessionScoreResponse,
} from "@/lib/api/types";
import { EvaluationStatus } from "@/lib/api/enums";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatDateTime, formatRelativeTime } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";
import { useToast } from "@/components/providers/ToastProvider";
import { useEvalRunTracker } from "@/components/providers/EvalRunTrackerProvider";
import { extractErrorMessage } from "@/lib/api/client";
import { ScoreRow, type ScoreItem } from "@/components/common/ScoreRow";

const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATES: ReadonlySet<string> = new Set([
  EvaluationStatus.COMPLETED,
  EvaluationStatus.FAILED,
]);

interface EvalRunDetailSidebarProps {
  mode: "trace" | "session";
  runId: string | null;
  open: boolean;
  onClose: () => void;
  /** Called after a successful retry or delete so the caller can invalidate its own queries. */
  onChanged?: () => void;
}

/**
 * Sidebar surface for drilling into a single trace or session evaluation
 * run. Fetches run metadata and scores (polling while still in-flight),
 * exposes retry/delete actions, and renders the scores using the same
 * rich `ScoreRow` component the trace/session detail sidebars use.
 */
export function EvalRunDetailSidebar({
  mode,
  runId,
  open,
  onClose,
  onChanged,
}: EvalRunDetailSidebarProps) {
  const { toast } = useToast();
  const tracker = useEvalRunTracker();
  const queryClient = useQueryClient();

  const [actionPending, setActionPending] = useState<"retry" | "delete" | null>(
    null,
  );
  const [confirmRetry, setConfirmRetry] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteScoresToo, setDeleteScoresToo] = useState(false);
  const [scoresOpen, setScoresOpen] = useState(false);

  const enabled = open && !!runId;

  // Reset the scores section back to collapsed whenever we switch runs or
  // the sidebar closes, so each run starts with the clean summary view.
  useEffect(() => {
    setScoresOpen(false);
  }, [runId]);

  const runQuery = useQuery<EvalRunResponse>({
    queryKey: ["evalRunDetail", mode, runId],
    queryFn: () =>
      mode === "trace" ? getTraceRun(runId!) : getSessionRun(runId!),
    enabled,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status && TERMINAL_STATES.has(status)) return false;
      return POLL_INTERVAL_MS;
    },
    refetchIntervalInBackground: false,
  });

  const scoresQuery = useQuery<TraceScoreResponse[] | SessionScoreResponse[]>({
    queryKey: ["evalRunScores", mode, runId],
    queryFn: () =>
      mode === "trace" ? getTraceRunScores(runId!) : getSessionRunScores(runId!),
    // Defer the fetch until the user expands the scores section, then keep
    // polling only while the section stays open and the run is still in-flight.
    enabled: enabled && scoresOpen,
    placeholderData: keepPreviousData,
    refetchInterval: () => {
      if (!scoresOpen) return false;
      const status = runQuery.data?.status;
      if (status && TERMINAL_STATES.has(status)) return false;
      return POLL_INTERVAL_MS;
    },
    refetchIntervalInBackground: false,
  });

  const run = runQuery.data;
  const scores = (scoresQuery.data ?? []) as ScoreItem[];

  const filtersList = useMemo<Array<[string, string]>>(() => {
    if (!run || !run.filters) return [];
    return Object.entries(run.filters)
      .filter(([, v]) => v !== null && v !== undefined && v !== "")
      .map(([k, v]) => [k, formatFilterValue(v)]);
  }, [run]);

  function refreshAll() {
    runQuery.refetch();
    // Only refetch scores if the user has actually opened the section; we
    // don't want the header's Refresh button to trigger a hidden fetch.
    if (scoresOpen) scoresQuery.refetch();
  }

  async function handleRetry() {
    if (!runId) return;
    setActionPending("retry");
    try {
      const response =
        mode === "trace"
          ? await retryTraceRun(runId)
          : await retrySessionRun(runId);
      tracker?.register({
        runId: response.id,
        mode,
        targetIds: [],
      });
      toast({ title: "Run retried", variant: "success" });
      await queryClient.invalidateQueries({
        queryKey: [mode === "trace" ? "traceRuns" : "sessionRuns"],
      });
      onChanged?.();
      onClose();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setActionPending(null);
      setConfirmRetry(false);
    }
  }

  async function handleDelete() {
    if (!runId) return;
    setActionPending("delete");
    try {
      if (mode === "trace") {
        await deleteTraceRun(runId, deleteScoresToo);
      } else {
        await deleteSessionRun(runId, deleteScoresToo);
      }
      toast({ title: "Run deleted", variant: "success" });
      await queryClient.invalidateQueries({
        queryKey: [mode === "trace" ? "traceRuns" : "sessionRuns"],
      });
      onChanged?.();
      onClose();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setActionPending(null);
      setConfirmDelete(false);
      setDeleteScoresToo(false);
    }
  }

  const title = run?.name || (run ? `Run ${run.id.slice(0, 8)}` : "Run");
  const isRefreshing =
    runQuery.isFetching || (scoresOpen && scoresQuery.isFetching);
  const hasFetchedScores = scoresQuery.data !== undefined;

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-bg/50" onClick={onClose} />
      )}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-[560px] max-w-[92vw] bg-surface border-l border-border",
          "flex flex-col transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between h-12 px-4 border-b border-border flex-shrink-0 gap-2">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider truncate">
            {title}
          </h2>
          <div className="flex items-center gap-1 flex-shrink-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={refreshAll}
              disabled={!runId || isRefreshing}
              aria-label="Refresh"
              title="Refresh"
            >
              <RefreshCw
                className={cn(
                  "h-3.5 w-3.5",
                  isRefreshing && "animate-spin",
                )}
              />
            </Button>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          {!runId ? null : runQuery.isPending ? (
            <div className="flex items-center justify-center h-24 text-xs text-text-muted font-mono">
              Loading run…
            </div>
          ) : runQuery.error ? (
            <div className="p-4 text-xs font-mono text-error">
              {extractErrorMessage(runQuery.error)}
            </div>
          ) : !run ? null : (
            <>
              <div className="px-4 py-3 border-b border-border space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <StatusBadge status={run.status} />
                  <Badge variant="default">{run.target_type}</Badge>
                  {run.monitor_id && (
                    <Badge
                      variant="default"
                      className="flex items-center gap-1"
                    >
                      <Radio className="h-2.5 w-2.5" />
                      monitor
                    </Badge>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <KVRow label="Progress">
                    <span className="text-text">
                      {run.evaluated_count}/{run.total_targets}
                    </span>
                    {run.failed_count > 0 && (
                      <span className="text-error ml-1">
                        ({run.failed_count} failed)
                      </span>
                    )}
                  </KVRow>
                  <KVRow label="Sampling">
                    <span className="text-text">
                      {formatSamplingRate(run.sampling_rate)}
                    </span>
                  </KVRow>
                  <KVRow label="Model">
                    <span className="text-text truncate">
                      {run.model ?? (
                        <span className="text-text-muted">default</span>
                      )}
                    </span>
                  </KVRow>
                  <KVRow label="Run ID">
                    <span
                      className="text-text-dim truncate"
                      title={run.id}
                    >
                      {run.id.slice(0, 8)}…
                    </span>
                  </KVRow>
                  <KVRow label="Created">
                    <span className="text-text flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" />
                      {formatDateTime(run.created_at)}
                    </span>
                  </KVRow>
                  <KVRow label="Completed">
                    {run.completed_at ? (
                      <span className="text-text flex items-center gap-1">
                        <Clock className="h-2.5 w-2.5" />
                        {formatRelativeTime(run.completed_at)}
                      </span>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </KVRow>
                </div>
              </div>

              <div className="px-4 py-3 border-b border-border">
                <label className="block text-[10px] font-mono text-text-muted uppercase tracking-wider mb-1.5">
                  Metrics
                </label>
                <div className="flex gap-1 flex-wrap">
                  {run.metric_names.length === 0 ? (
                    <span className="text-[11px] font-mono text-text-muted">
                      None
                    </span>
                  ) : (
                    run.metric_names.map((m) => (
                      <Badge key={m} variant="info">
                        {m}
                      </Badge>
                    ))
                  )}
                </div>
              </div>

              {filtersList.length > 0 && (
                <div className="px-4 py-3 border-b border-border">
                  <label className="flex items-center gap-1 text-[10px] font-mono text-text-muted uppercase tracking-wider mb-1.5">
                    <Filter className="h-2.5 w-2.5" />
                    Filters
                  </label>
                  <div className="border border-border/40">
                    <table className="text-[11px] font-mono w-full border-collapse">
                      <tbody>
                        {filtersList.map(([key, val]) => (
                          <tr
                            key={key}
                            className="border-b border-border/40 last:border-0"
                          >
                            <td className="text-text-muted px-2 py-0.5 whitespace-nowrap align-top border-r border-border/40">
                              {key}
                            </td>
                            <td className="text-text px-2 py-0.5 break-all">
                              {val}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {run.error_message && (
                <div className="px-4 py-3 border-b border-border">
                  <label className="block text-[10px] font-mono text-text-muted uppercase tracking-wider mb-1.5">
                    Error
                  </label>
                  <div className="bg-error/5 border border-error/20 p-2">
                    <span className="text-[11px] font-mono text-error whitespace-pre-wrap">
                      {run.error_message}
                    </span>
                  </div>
                </div>
              )}

              <div className="px-4 py-3 border-b border-border flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setConfirmRetry(true)}
                  disabled={actionPending !== null}
                >
                  {actionPending === "retry" ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <RotateCw className="h-3 w-3" />
                  )}
                  Retry
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setConfirmDelete(true)}
                  disabled={actionPending !== null}
                >
                  {actionPending === "delete" ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Trash2 className="h-3 w-3" />
                  )}
                  Delete
                </Button>
              </div>

              <div>
                <button
                  type="button"
                  onClick={() => setScoresOpen((v) => !v)}
                  aria-expanded={scoresOpen}
                  className="w-full flex items-center justify-between h-10 px-4 border-b border-border hover:bg-surface-hi transition-colors focus:outline-none focus-visible:bg-surface-hi"
                >
                  <h3 className="text-xs font-mono text-text-muted uppercase tracking-wider flex items-center gap-1.5">
                    {scoresOpen ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                    Scores
                    {hasFetchedScores && (
                      <span className="text-text-dim normal-case tracking-normal">
                        · {scores.length}
                      </span>
                    )}
                  </h3>
                  {scoresOpen && scoresQuery.isFetching && (
                    <Loader2 className="h-3 w-3 animate-spin text-text-muted" />
                  )}
                </button>
                {scoresOpen &&
                  (scoresQuery.error ? (
                    <div className="p-4 text-xs font-mono text-error">
                      {extractErrorMessage(scoresQuery.error)}
                    </div>
                  ) : !hasFetchedScores ? (
                    <div className="p-4 text-xs font-mono text-text-muted">
                      Loading scores…
                    </div>
                  ) : scores.length === 0 ? (
                    <div className="p-4 text-xs font-mono text-text-muted">
                      {TERMINAL_STATES.has(run.status)
                        ? "This run produced no scores."
                        : "Scores will appear here as they are produced."}
                    </div>
                  ) : (
                    <div className="divide-y divide-border">
                      {scores.map((score) => (
                        <ScoreRow
                          key={score.id}
                          score={score}
                          onScoreUpdated={() => scoresQuery.refetch()}
                          onScoreDeleted={() => scoresQuery.refetch()}
                        />
                      ))}
                    </div>
                  ))}
              </div>
            </>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmRetry}
        onOpenChange={(v) => {
          if (!v && actionPending === "retry") return;
          setConfirmRetry(v);
        }}
        title="Retry run"
        description="A new evaluation run will be queued with the same configuration. Continue?"
        confirmLabel="Retry"
        onConfirm={handleRetry}
      />

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={(v) => {
          if (!v && actionPending === "delete") return;
          setConfirmDelete(v);
          if (!v) setDeleteScoresToo(false);
        }}
        title="Delete run"
        description={
          <div className="space-y-3">
            <p>
              Delete this evaluation run? This action cannot be undone.
            </p>
            <label className="flex items-center gap-2 text-xs font-mono text-text-muted cursor-pointer">
              <input
                type="checkbox"
                checked={deleteScoresToo}
                onChange={(e) => setDeleteScoresToo(e.target.checked)}
              />
              <span>Also delete scores produced by this run</span>
            </label>
          </div>
        }
        confirmLabel="Delete"
        onConfirm={handleDelete}
        destructive
      />
    </>
  );
}

function KVRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <span className="text-[10px] text-text-muted uppercase tracking-wider block">
        {label}
      </span>
      <div className="truncate">{children}</div>
    </div>
  );
}

function formatSamplingRate(rate: number): string {
  if (rate == null || Number.isNaN(rate)) return "—";
  if (rate >= 1) return "100%";
  return `${Math.round(rate * 100)}%`;
}

function formatFilterValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (Array.isArray(v)) return v.map((x) => String(x)).join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

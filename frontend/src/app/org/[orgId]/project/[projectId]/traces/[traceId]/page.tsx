"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Trash2,
  Copy,
  Check,
  BarChart3,
  FlaskConical,
  Loader2,
  ChevronDown,
} from "lucide-react";
import { getTrace, deleteTrace } from "@/lib/api/traces";
import { getTraceScoresByTraceId } from "@/lib/api/evaluations";
import { queryKeys } from "@/lib/query/keys";
import { SpanWaterfall } from "@/components/features/SpanWaterfall";
import { ScoresSidebar } from "@/components/features/ScoresSidebar";
import { EvaluationSidebar } from "@/components/features/EvaluationSidebar";
import { useHasPendingEvalForTarget } from "@/components/providers/EvalRunTrackerProvider";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Tooltip } from "@/components/ui/Tooltip";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useToast } from "@/components/providers/ToastProvider";
import {
  formatDateTime,
  formatDuration,
  // TODO(cost): re-enable when trace cost computation is implemented.
  // formatCost,
  formatTokens,
} from "@/lib/utils/format";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useProjectPath, useProjectId } from "@/hooks/useNavigation";
import { extractErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";

export default function TraceDetailPage({
  params,
}: {
  params: Promise<{ traceId: string }>;
}) {
  const { traceId } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const projectPath = useProjectPath();
  const projectId = useProjectId() ?? "";

  useDocumentTitle("Trace Detail");

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const [scoresOpen, setScoresOpen] = useState(false);
  const [runEvalOpen, setRunEvalOpen] = useState(false);

  const hasPendingEval = useHasPendingEvalForTarget("trace", traceId);

  const traceQuery = useQuery({
    queryKey: queryKeys.traces.detail(traceId),
    queryFn: () => getTrace(traceId),
  });

  const scoresQuery = useQuery({
    queryKey: [...queryKeys.traces.detail(traceId), "scores"],
    queryFn: () => getTraceScoresByTraceId(traceId).catch(() => []),
  });

  async function handleDelete() {
    try {
      await deleteTrace(traceId);
      queryClient.invalidateQueries({
        queryKey: queryKeys.traces.all(projectId),
      });
      toast({ title: "Trace deleted", variant: "success" });
      router.push(projectPath + "/traces");
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  function handleCopyId() {
    navigator.clipboard.writeText(traceId);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  }

  if (traceQuery.isPending) return <LoadingState />;
  if (traceQuery.error)
    return <ErrorState message={extractErrorMessage(traceQuery.error)} />;

  const trace = traceQuery.data;
  if (!trace) return <ErrorState message="Trace not found" />;

  const scores = scoresQuery.data ?? [];

  const latencyMs =
    trace.started_at && trace.ended_at
      ? new Date(trace.ended_at).getTime() -
        new Date(trace.started_at).getTime()
      : null;

  return (
    <div className="flex h-full min-h-[540px] flex-col gap-3 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-2 shrink-0">
        <div className="flex min-w-0 items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Go back"
            onClick={() => router.back()}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1
            className="truncate text-lg font-mono text-primary"
            title={trace.name}
          >
            {trace.name}
          </h1>
          <div className="hidden xl:flex items-center gap-1.5">
            <span
              className="text-xs text-text-muted font-mono"
              title={trace.trace_id}
            >
              {trace.trace_id.slice(0, 8)}
            </span>
            <Tooltip content={copiedId ? "Copied!" : "Copy trace ID"}>
              <button
                className="text-text-muted hover:text-text transition-colors"
                onClick={handleCopyId}
                aria-label="Copy trace ID"
              >
                {copiedId ? (
                  <Check className="h-3 w-3 text-success" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </button>
            </Tooltip>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            className="px-2 sm:px-3"
            onClick={() => setRunEvalOpen(true)}
          >
            <FlaskConical className="h-3 w-3" />
            Evaluate
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setScoresOpen((v) => !v)}
            disabled={scores.length === 0 && !hasPendingEval}
            className={cn(
              "px-2 sm:px-3",
              scores.length > 0 || hasPendingEval
                ? "text-info border-info/30 hover:bg-info/10"
                : "text-text-muted border-border opacity-50 cursor-not-allowed",
            )}
          >
            <BarChart3 className="h-3 w-3" />
            Scores
            {scores.length > 0 && (
              <Badge variant="info" className="ml-0.5 px-1.5 py-0">
                {scores.length}
              </Badge>
            )}
            {hasPendingEval && (
              <Loader2 className="h-3 w-3 animate-spin text-info" />
            )}
          </Button>
          <Button
            variant="destructive"
            size="sm"
            className="px-2 sm:px-3"
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 className="h-3 w-3" /> Delete
          </Button>
        </div>
      </div>

      <details className="group shrink-0 border border-border bg-surface text-xs font-mono">
        <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2 [&::-webkit-details-marker]:hidden focus-visible:outline focus-visible:outline-primary">
          <StatusBadge status={trace.status} />
          <span className="text-text">
            {formatDuration(latencyMs)}{" "}
            <span className="text-text-muted">duration</span>
          </span>
          <span className="text-text">
            {formatTokens(trace.total_tokens)}{" "}
            <span className="text-text-muted">tokens</span>
          </span>
          <span className="ml-auto flex items-center gap-2 text-text-dim">
            Trace details{" "}
            <ChevronDown className="h-3 w-3 group-open:rotate-180" />
          </span>
        </summary>
        <div className="grid max-h-[28vh] grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 overflow-auto border-t border-divider p-3 text-xs font-mono [overflow-wrap:anywhere]">
          <div className="sm:col-span-2">
            <span className="text-text-muted block">Trace ID</span>
            <button
              type="button"
              onClick={handleCopyId}
              className="text-left text-text hover:text-primary"
              title="Copy trace ID"
            >
              {trace.trace_id}{" "}
              {copiedId ? "Copied" : <Copy className="inline h-3 w-3" />}
            </button>
          </div>
          {/* TODO(cost): Restore Total Cost once trace cost computation is implemented. */}
          {/* <div>
            <span className="text-text-muted block">Total Cost</span>
            <span className="text-text">{formatCost(trace.total_cost)}</span>
          </div> */}
          <div>
            <span className="text-text-muted block">Started</span>
            <span className="text-text">
              {formatDateTime(trace.started_at)}
            </span>
          </div>
          <div>
            <span className="text-text-muted block">Ended</span>
            <span className="text-text">{formatDateTime(trace.ended_at)}</span>
          </div>
          <div>
            <span className="text-text-muted block">Session</span>
            <span className="text-text">{trace.session_id ?? "—"}</span>
          </div>
          <div>
            <span className="text-text-muted block">User</span>
            <span className="ph-no-capture text-text">
              {trace.user_id ?? "—"}
            </span>
          </div>
          <div>
            <span className="text-text-muted block">Environment</span>
            <span className="text-text">{trace.environment ?? "—"}</span>
          </div>
          <div>
            <span className="text-text-muted block">Release</span>
            <span className="text-text">{trace.release ?? "—"}</span>
          </div>
          <div className="sm:col-span-2">
            <span className="text-text-muted block mb-1">Tags</span>
            {trace.tags.length > 0 ? (
              <div className="flex gap-1 flex-wrap">
                {trace.tags.map((tag) => (
                  <Badge key={tag} variant="default">
                    {tag}
                  </Badge>
                ))}
              </div>
            ) : (
              <span className="text-text">—</span>
            )}
          </div>
        </div>
      </details>

      <SpanWaterfall key={trace.trace_id} trace={trace} />

      <ScoresSidebar
        scores={scores}
        open={scoresOpen}
        onClose={() => setScoresOpen(false)}
        onScoreUpdated={() =>
          queryClient.invalidateQueries({
            queryKey: [...queryKeys.traces.detail(traceId), "scores"],
          })
        }
        onScoreDeleted={() =>
          queryClient.invalidateQueries({
            queryKey: [...queryKeys.traces.detail(traceId), "scores"],
          })
        }
        onRefresh={() =>
          queryClient.invalidateQueries({
            queryKey: [...queryKeys.traces.detail(traceId), "scores"],
          })
        }
        isRefreshing={scoresQuery.isFetching}
      />

      <EvaluationSidebar
        mode="trace"
        open={runEvalOpen}
        onClose={() => setRunEvalOpen(false)}
        targetIds={[traceId]}
        onSubmitted={() =>
          queryClient.invalidateQueries({
            queryKey: queryKeys.evaluations.traceRuns.all(projectId),
          })
        }
      />

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete trace"
        description="Are you sure you want to delete this trace? This action cannot be undone."
        confirmLabel="Delete"
        onConfirm={handleDelete}
        destructive
      />
    </div>
  );
}

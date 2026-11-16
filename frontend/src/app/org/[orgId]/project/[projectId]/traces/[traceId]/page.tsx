"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Trash2,
  Link,
  Check,
  BarChart3,
  FlaskConical,
  Loader2,
} from "lucide-react";
import { getTrace, deleteTrace } from "@/lib/api/traces";
import { getTraceScoresByTraceId } from "@/lib/api/evaluations";
import { queryKeys } from "@/lib/query/keys";
import { SpanWaterfall } from "@/components/features/SpanWaterfall";
import { ScoresSidebar } from "@/components/features/ScoresSidebar";
import { EvaluationSidebar } from "@/components/features/EvaluationSidebar";
import { TraceMetadataSidebar } from "@/components/features/TraceMetadataSidebar";
import { useHasPendingEvalForTarget } from "@/components/providers/EvalRunTrackerProvider";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Tooltip } from "@/components/ui/Tooltip";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useToast } from "@/components/providers/ToastProvider";
import { formatDuration, formatTokens } from "@/lib/utils/format";
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

  async function handleCopyId() {
    try {
      await navigator.clipboard.writeText(traceId);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    } catch {
      toast({ title: "Could not copy trace ID", variant: "error" });
    }
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
      <div className="grid shrink-0 grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center min-[1360px]:flex min-[1360px]:gap-4">
        <div className="flex min-w-0 items-center gap-2 min-[1360px]:max-w-[28%]">
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
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
          <Tooltip content={copiedId ? "Copied!" : "Copy trace ID"}>
            <Button
              variant="ghost"
              size="sm"
              className="shrink-0 gap-1.5 px-1.5 text-text-muted"
              onClick={handleCopyId}
              aria-label="Copy trace ID"
            >
              ID
              {copiedId ? (
                <Check className="h-3 w-3 text-success" />
              ) : (
                <Link className="h-3 w-3" />
              )}
            </Button>
          </Tooltip>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs font-mono lg:col-span-2 lg:row-start-2 min-[1360px]:shrink-0">
          <StatusBadge status={trace.status} />
          <span className="whitespace-nowrap text-text">
            {formatDuration(latencyMs)}{" "}
            <span className="text-text-muted">duration</span>
          </span>
          <span className="whitespace-nowrap text-text">
            {formatTokens(trace.total_tokens)}{" "}
            <span className="text-text-muted">tokens</span>
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 lg:col-start-2 lg:row-start-1 lg:flex-nowrap min-[1360px]:ml-auto min-[1360px]:shrink-0">
          <TraceMetadataSidebar
            trace={trace}
            copiedId={copiedId}
            onCopyId={handleCopyId}
          />
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

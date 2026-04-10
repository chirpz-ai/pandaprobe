"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trash2 } from "lucide-react";
import { getTrace, deleteTrace } from "@/lib/api/traces";
import { getTraceScoresByTraceId } from "@/lib/api/evaluations";
import { queryKeys } from "@/lib/query/keys";
import { SpanTreeView } from "@/components/features/SpanTreeView";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useToast } from "@/components/providers/ToastProvider";
import { formatDateTime, formatDuration } from "@/lib/utils/format";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useProjectPath, useProjectId } from "@/hooks/useNavigation";
import { extractErrorMessage } from "@/lib/api/client";

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

  if (traceQuery.isPending) return <LoadingState />;
  if (traceQuery.error)
    return (
      <ErrorState message={extractErrorMessage(traceQuery.error)} />
    );

  const trace = traceQuery.data;
  if (!trace) return <ErrorState message="Trace not found" />;

  const scores = scoresQuery.data ?? [];

  const latencyMs =
    trace.started_at && trace.ended_at
      ? new Date(trace.ended_at).getTime() -
        new Date(trace.started_at).getTime()
      : null;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-lg font-mono text-primary">{trace.name}</h1>
            <span className="text-xs text-text-muted font-mono">
              {trace.trace_id}
            </span>
          </div>
        </div>
        <Button
          variant="destructive"
          size="sm"
          onClick={() => setConfirmDelete(true)}
        >
          <Trash2 className="h-3 w-3" /> Delete
        </Button>
      </div>

      <div className="border-engraved bg-surface p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
          <div>
            <span className="text-text-muted block">Status</span>
            <StatusBadge status={trace.status} />
          </div>
          <div>
            <span className="text-text-muted block">Latency</span>
            <span className="text-text">{formatDuration(latencyMs)}</span>
          </div>
          <div>
            <span className="text-text-muted block">Started</span>
            <span className="text-text">
              {formatDateTime(trace.started_at)}
            </span>
          </div>
          <div>
            <span className="text-text-muted block">Ended</span>
            <span className="text-text">
              {formatDateTime(trace.ended_at)}
            </span>
          </div>
          {trace.session_id && (
            <div>
              <span className="text-text-muted block">Session</span>
              <span className="text-text">{trace.session_id}</span>
            </div>
          )}
          {trace.user_id && (
            <div>
              <span className="text-text-muted block">User</span>
              <span className="text-text">{trace.user_id}</span>
            </div>
          )}
          {trace.environment && (
            <div>
              <span className="text-text-muted block">Environment</span>
              <span className="text-text">{trace.environment}</span>
            </div>
          )}
          {trace.tags.length > 0 && (
            <div className="col-span-2">
              <span className="text-text-muted block mb-1">Tags</span>
              <div className="flex gap-1 flex-wrap">
                {trace.tags.map((tag) => (
                  <Badge key={tag} variant="default">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {trace.input != null && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-2">
            Input
          </h2>
          <pre className="text-xs text-text-dim overflow-auto max-h-48 bg-bg p-3 border border-border">
            {typeof trace.input === "string"
              ? trace.input
              : JSON.stringify(trace.input, null, 2)}
          </pre>
        </div>
      )}

      {trace.output != null && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-2">
            Output
          </h2>
          <pre className="text-xs text-text-dim overflow-auto max-h-48 bg-bg p-3 border border-border">
            {typeof trace.output === "string"
              ? trace.output
              : JSON.stringify(trace.output, null, 2)}
          </pre>
        </div>
      )}

      {scores.length > 0 && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
            Scores
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {scores.map((score) => (
              <div key={score.id} className="border border-border p-2">
                <span className="text-xs text-text-muted block">
                  {score.name}
                </span>
                <span className="text-sm font-mono text-text">
                  {score.value ?? "—"}
                </span>
                <StatusBadge status={score.status} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
          Span Tree ({trace.spans.length} spans)
        </h2>
        <SpanTreeView spans={trace.spans} />
      </div>

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

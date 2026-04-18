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
} from "lucide-react";
import { getSession, deleteSession } from "@/lib/api/sessions";
import { getSessionScoresBySessionId } from "@/lib/api/evaluations";
import { queryKeys } from "@/lib/query/keys";
import { TraceTable } from "@/components/features/TraceTable";
import { ScoresSidebar } from "@/components/features/ScoresSidebar";
import { RunEvalSidebar } from "@/components/features/RunEvalSidebar";
import { Pagination } from "@/components/common/Pagination";
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
  formatCost,
  formatTokens,
} from "@/lib/utils/format";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useProjectPath, useProjectId } from "@/hooks/useNavigation";
import { extractErrorMessage } from "@/lib/api/client";
import { useUrlState } from "@/hooks/useUrlState";
import { cn } from "@/lib/utils/cn";

const URL_CONFIG = {
  page: { default: "1" },
  limit: { default: "50" },
} as const;

export default function SessionDetailPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const projectPath = useProjectPath();
  const projectId = useProjectId() ?? "";

  useDocumentTitle("Session Detail");

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const [scoresOpen, setScoresOpen] = useState(false);
  const [runEvalOpen, setRunEvalOpen] = useState(false);

  const { page, limit, offset, setPage, totalPages, set } =
    useUrlState(URL_CONFIG);

  const {
    data: session,
    isPending,
    error,
  } = useQuery({
    queryKey: [...queryKeys.sessions.detail(sessionId), { limit, offset }],
    queryFn: () => getSession(sessionId, { limit, offset }),
  });

  const scoresQuery = useQuery({
    queryKey: [...queryKeys.sessions.detail(sessionId), "scores"],
    queryFn: () => getSessionScoresBySessionId(sessionId).catch(() => []),
  });

  async function handleDelete() {
    try {
      await deleteSession(sessionId);
      queryClient.invalidateQueries({
        queryKey: queryKeys.sessions.all(projectId),
      });
      toast({ title: "Session deleted", variant: "success" });
      router.push(projectPath + "/sessions");
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  function handleCopyId() {
    navigator.clipboard.writeText(sessionId);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  }

  if (isPending) return <LoadingState />;
  if (error) return <ErrorState message={extractErrorMessage(error)} />;
  if (!session) return <ErrorState message="Session not found" />;

  const scores = scoresQuery.data ?? [];

  const traceListItems = session.traces.map((t) => ({
    trace_id: t.trace_id,
    name: t.name,
    status: t.status,
    started_at: t.started_at,
    ended_at: t.ended_at,
    session_id: t.session_id,
    user_id: t.user_id,
    tags: t.tags,
    environment: t.environment,
    release: t.release,
    latency_ms:
      t.started_at && t.ended_at
        ? new Date(t.ended_at).getTime() - new Date(t.started_at).getTime()
        : null,
    span_count: t.spans.length,
    total_tokens: t.total_tokens,
    total_cost: t.total_cost,
  }));

  return (
    <div className="flex flex-col h-[calc(100vh-96px)] animate-fade-in">
      <div className="flex-shrink-0 space-y-6 pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => router.back()}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <h1 className="text-lg font-mono text-primary">Session</h1>
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-muted font-mono">
                {session.session_id}
              </span>
              <Tooltip content={copiedId ? "Copied!" : "Copy session ID"}>
                <button
                  className="text-text-muted hover:text-text transition-colors"
                  onClick={handleCopyId}
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
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setRunEvalOpen(true)}
            >
              <FlaskConical className="h-3 w-3" />
              Evaluation
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setScoresOpen((v) => !v)}
              disabled={scores.length === 0}
              className={cn(
                scores.length > 0
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
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 className="h-3 w-3" /> Delete
            </Button>
          </div>
        </div>

        <div className="border-engraved bg-surface p-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
            <div>
              <span className="text-text-muted block">Traces</span>
              <span className="text-text">{session.trace_count}</span>
            </div>
            <div>
              <span className="text-text-muted block">Total Spans</span>
              <span className="text-text">{session.total_span_count}</span>
            </div>
            <div>
              <span className="text-text-muted block">Error</span>
              <Badge variant={session.has_error ? "error" : "success"}>
                {session.has_error ? "Yes" : "No"}
              </Badge>
            </div>
            <div>
              <span className="text-text-muted block">Total Latency</span>
              <span className="text-text">
                {formatDuration(session.total_latency_ms)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block">Total Tokens</span>
              <span className="text-text">
                {formatTokens(session.total_tokens)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block">Total Cost</span>
              <span className="text-text">
                {formatCost(session.total_cost)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block">First Trace</span>
              <span className="text-text">
                {formatDateTime(session.first_trace_at)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block">Last Trace</span>
              <span className="text-text">
                {formatDateTime(session.last_trace_at)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block">User</span>
              <span className="text-text">{session.user_id ?? "—"}</span>
            </div>
            <div className="col-span-2">
              <span className="text-text-muted block mb-1">Tags</span>
              {session.tags.length > 0 ? (
                <div className="flex gap-1 flex-wrap">
                  {session.tags.map((tag) => (
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
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        <div className="flex-shrink-0 pb-2">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider">
            Traces · {session.trace_count}
          </h2>
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto">
          <TraceTable traces={traceListItems} />
        </div>
        <Pagination
          page={page}
          totalPages={totalPages(session.trace_count)}
          onPageChange={setPage}
          total={session.trace_count}
          limit={limit}
          onLimitChange={(n) => set({ limit: String(n), page: "1" })}
        />
      </div>

      <ScoresSidebar
        scores={scores}
        open={scoresOpen}
        onClose={() => setScoresOpen(false)}
        onScoreDeleted={() =>
          queryClient.invalidateQueries({
            queryKey: [...queryKeys.sessions.detail(sessionId), "scores"],
          })
        }
        onRefresh={() =>
          queryClient.invalidateQueries({
            queryKey: [...queryKeys.sessions.detail(sessionId), "scores"],
          })
        }
        isRefreshing={scoresQuery.isFetching}
      />

      <RunEvalSidebar
        mode="session"
        open={runEvalOpen}
        onClose={() => setRunEvalOpen(false)}
        targetIds={[sessionId]}
        onSubmitted={() =>
          queryClient.invalidateQueries({
            queryKey: queryKeys.evaluations.sessionRuns.all(projectId),
          })
        }
      />

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete session"
        description="Delete this session and all associated traces? This cannot be undone."
        confirmLabel="Delete"
        onConfirm={handleDelete}
        destructive
      />
    </div>
  );
}

"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trash2 } from "lucide-react";
import { getSession, deleteSession } from "@/lib/api/sessions";
import { queryKeys } from "@/lib/query/keys";
import { TraceTable } from "@/components/features/TraceTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useToast } from "@/components/providers/ToastProvider";
import { formatDateTime, formatDuration, formatCost } from "@/lib/utils/format";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useProjectPath, useProjectId } from "@/hooks/useNavigation";
import { extractErrorMessage } from "@/lib/api/client";

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

  const {
    data: session,
    isPending,
    error,
  } = useQuery({
    queryKey: queryKeys.sessions.detail(sessionId),
    queryFn: () => getSession(sessionId),
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

  if (isPending) return <LoadingState />;
  if (error) return <ErrorState message={extractErrorMessage(error)} />;
  if (!session) return <ErrorState message="Session not found" />;

  const traceListItems = session.traces.map((t) => {
    return {
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
    };
  });

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-lg font-mono text-primary">Session</h1>
            <span className="text-xs text-text-muted font-mono">
              {session.session_id}
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
            <span className="text-text-muted block">Traces</span>
            <span className="text-text">{session.trace_count}</span>
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
            <span className="text-text-muted block">Cost</span>
            <span className="text-text">{formatCost(session.total_cost)}</span>
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
          {session.user_id && (
            <div>
              <span className="text-text-muted block">User</span>
              <span className="text-text">{session.user_id}</span>
            </div>
          )}
        </div>
      </div>

      <div>
        <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
          Traces ({session.trace_count})
        </h2>
        <TraceTable traces={traceListItems} />
      </div>

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

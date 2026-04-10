"use client";

import { useEffect, useState, useCallback } from "react";
import { useProject } from "@/components/providers/ProjectProvider";
import { listTraceRuns, deleteTraceRun, retryTraceRun } from "@/lib/api/evaluations";
import type { EvalRunResponse, PaginatedResponse } from "@/lib/api/types";
import { EvalRunTable } from "@/components/features/EvalRunTable";
import { Pagination } from "@/components/common/Pagination";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { usePagination } from "@/hooks/usePagination";
import { useToast } from "@/components/providers/ToastProvider";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { formatDateTime } from "@/lib/utils/format";
import * as Dialog from "@radix-ui/react-dialog";
import { X, RotateCw, Trash2 } from "lucide-react";

export default function TraceRunsPage() {
  const { currentProject } = useProject();
  const { toast } = useToast();
  const pagination = usePagination();

  const [data, setData] = useState<PaginatedResponse<EvalRunResponse> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<EvalRunResponse | null>(null);

  const fetchData = useCallback(async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const result = await listTraceRuns({
        limit: pagination.limit,
        offset: pagination.offset,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load runs");
    } finally {
      setLoading(false);
    }
  }, [currentProject, pagination.limit, pagination.offset]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleRetry(runId: string) {
    try {
      await retryTraceRun(runId);
      toast({ title: "Run retried", variant: "success" });
      fetchData();
    } catch {
      toast({ title: "Failed to retry run", variant: "error" });
    }
  }

  async function handleDelete(runId: string) {
    try {
      await deleteTraceRun(runId, false);
      toast({ title: "Run deleted", variant: "success" });
      setSelected(null);
      fetchData();
    } catch {
      toast({ title: "Failed to delete run", variant: "error" });
    }
  }

  if (!currentProject) {
    return <EmptyState title="Select a project" description="Choose a project to view trace evaluation runs." />;
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Trace Evaluation Runs</h1>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchData} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No evaluation runs" description="Create an evaluation run to get started." />
      ) : (
        <>
          <EvalRunTable runs={data.items} onSelect={setSelected} />
          <Pagination
            page={pagination.page}
            totalPages={pagination.totalPages(data.total)}
            onPageChange={pagination.setPage}
            total={data.total}
          />
        </>
      )}

      <Dialog.Root open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 border border-border bg-surface p-6 animate-fade-in">
            {selected && (
              <>
                <div className="flex items-start justify-between mb-4">
                  <Dialog.Title className="text-sm font-mono text-primary">
                    {selected.name || `Run ${selected.id.slice(0, 8)}`}
                  </Dialog.Title>
                  <Dialog.Close className="text-text-muted hover:text-text">
                    <X className="h-4 w-4" />
                  </Dialog.Close>
                </div>
                <div className="space-y-3 text-xs font-mono">
                  <div className="flex gap-2">
                    <StatusBadge status={selected.status} />
                    <Badge variant="default">{selected.target_type}</Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-text-muted block">Progress</span>
                      <span className="text-text">{selected.evaluated_count}/{selected.total_targets}</span>
                    </div>
                    <div>
                      <span className="text-text-muted block">Failed</span>
                      <span className="text-error">{selected.failed_count}</span>
                    </div>
                    <div>
                      <span className="text-text-muted block">Created</span>
                      <span className="text-text">{formatDateTime(selected.created_at)}</span>
                    </div>
                    <div>
                      <span className="text-text-muted block">Completed</span>
                      <span className="text-text">{formatDateTime(selected.completed_at)}</span>
                    </div>
                  </div>
                  <div>
                    <span className="text-text-muted block mb-1">Metrics</span>
                    <div className="flex gap-1 flex-wrap">
                      {selected.metric_names.map((m) => (
                        <Badge key={m} variant="info">{m}</Badge>
                      ))}
                    </div>
                  </div>
                  {selected.error_message && (
                    <div className="bg-error/5 border border-error/20 p-2">
                      <span className="text-error">{selected.error_message}</span>
                    </div>
                  )}
                  <div className="flex gap-2 pt-2">
                    <Button variant="secondary" size="sm" onClick={() => handleRetry(selected.id)}>
                      <RotateCw className="h-3 w-3" /> Retry
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => handleDelete(selected.id)}>
                      <Trash2 className="h-3 w-3" /> Delete
                    </Button>
                  </div>
                </div>
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}

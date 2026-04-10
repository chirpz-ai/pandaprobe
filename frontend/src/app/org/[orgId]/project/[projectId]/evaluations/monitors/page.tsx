"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useProject } from "@/components/providers/ProjectProvider";
import {
  listMonitors,
  pauseMonitor,
  resumeMonitor,
  triggerMonitor,
  deleteMonitor,
} from "@/lib/api/evaluations";
import { MonitorCard } from "@/components/features/MonitorCard";
import { Pagination } from "@/components/common/Pagination";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { usePagination } from "@/hooks/usePagination";
import { useToast } from "@/components/providers/ToastProvider";
import { queryKeys } from "@/lib/query/keys";

export default function MonitorsPage() {
  const { currentProject } = useProject();
  const { toast } = useToast();
  const pagination = usePagination(20);
  const queryClient = useQueryClient();
  const projectId = currentProject?.id ?? "";

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.evaluations.monitors(projectId),
    queryFn: () => listMonitors({ limit: pagination.limit, offset: pagination.offset }),
    enabled: !!currentProject,
  });

  async function handlePause(id: string) {
    try {
      await pauseMonitor(id);
      toast({ title: "Monitor paused", variant: "success" });
      queryClient.invalidateQueries({ queryKey: queryKeys.evaluations.monitors(projectId) });
    } catch {
      toast({ title: "Failed to pause monitor", variant: "error" });
    }
  }

  async function handleResume(id: string) {
    try {
      await resumeMonitor(id);
      toast({ title: "Monitor resumed", variant: "success" });
      queryClient.invalidateQueries({ queryKey: queryKeys.evaluations.monitors(projectId) });
    } catch {
      toast({ title: "Failed to resume monitor", variant: "error" });
    }
  }

  async function handleTrigger(id: string) {
    try {
      await triggerMonitor(id);
      toast({ title: "Monitor triggered", variant: "success" });
      queryClient.invalidateQueries({ queryKey: queryKeys.evaluations.monitors(projectId) });
    } catch {
      toast({ title: "Failed to trigger monitor", variant: "error" });
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteMonitor(id);
      toast({ title: "Monitor deleted", variant: "success" });
      queryClient.invalidateQueries({ queryKey: queryKeys.evaluations.monitors(projectId) });
    } catch {
      toast({ title: "Failed to delete monitor", variant: "error" });
    }
  }

  if (!currentProject) {
    return <EmptyState title="Select a project" description="Choose a project to view monitors." />;
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Monitors</h1>

      {isPending ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error instanceof Error ? error.message : "Failed to load monitors"} onRetry={() => refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No monitors" description="Create a monitor to automate evaluations." />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.items.map((monitor) => (
              <MonitorCard
                key={monitor.id}
                monitor={monitor}
                onPause={handlePause}
                onResume={handleResume}
                onTrigger={handleTrigger}
                onDelete={handleDelete}
              />
            ))}
          </div>
          <Pagination
            page={pagination.page}
            totalPages={pagination.totalPages(data.total)}
            onPageChange={pagination.setPage}
            total={data.total}
          />
        </>
      )}
    </div>
  );
}

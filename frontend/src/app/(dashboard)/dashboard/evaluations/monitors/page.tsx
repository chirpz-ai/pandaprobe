"use client";

import { useEffect, useState, useCallback } from "react";
import { useProject } from "@/components/providers/ProjectProvider";
import {
  listMonitors,
  pauseMonitor,
  resumeMonitor,
  triggerMonitor,
  deleteMonitor,
} from "@/lib/api/evaluations";
import type { MonitorResponse, PaginatedResponse } from "@/lib/api/types";
import { MonitorCard } from "@/components/organisms/MonitorCard";
import { Pagination } from "@/components/molecules/Pagination";
import { LoadingState } from "@/components/molecules/LoadingState";
import { ErrorState } from "@/components/molecules/ErrorState";
import { EmptyState } from "@/components/molecules/EmptyState";
import { usePagination } from "@/hooks/usePagination";
import { useToast } from "@/components/providers/ToastProvider";

export default function MonitorsPage() {
  const { currentProject } = useProject();
  const { toast } = useToast();
  const pagination = usePagination(20);

  const [data, setData] = useState<PaginatedResponse<MonitorResponse> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const result = await listMonitors({
        limit: pagination.limit,
        offset: pagination.offset,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load monitors");
    } finally {
      setLoading(false);
    }
  }, [currentProject, pagination.limit, pagination.offset]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handlePause(id: string) {
    try {
      await pauseMonitor(id);
      toast({ title: "Monitor paused", variant: "success" });
      fetchData();
    } catch {
      toast({ title: "Failed to pause monitor", variant: "error" });
    }
  }

  async function handleResume(id: string) {
    try {
      await resumeMonitor(id);
      toast({ title: "Monitor resumed", variant: "success" });
      fetchData();
    } catch {
      toast({ title: "Failed to resume monitor", variant: "error" });
    }
  }

  async function handleTrigger(id: string) {
    try {
      await triggerMonitor(id);
      toast({ title: "Monitor triggered", variant: "success" });
      fetchData();
    } catch {
      toast({ title: "Failed to trigger monitor", variant: "error" });
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteMonitor(id);
      toast({ title: "Monitor deleted", variant: "success" });
      fetchData();
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

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchData} />
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

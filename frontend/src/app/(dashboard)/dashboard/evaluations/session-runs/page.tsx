"use client";

import { useEffect, useState, useCallback } from "react";
import { useProject } from "@/components/providers/ProjectProvider";
import { listSessionRuns } from "@/lib/api/evaluations";
import type { EvalRunResponse, PaginatedResponse } from "@/lib/api/types";
import { EvalRunTable } from "@/components/organisms/EvalRunTable";
import { Pagination } from "@/components/molecules/Pagination";
import { LoadingState } from "@/components/molecules/LoadingState";
import { ErrorState } from "@/components/molecules/ErrorState";
import { EmptyState } from "@/components/molecules/EmptyState";
import { usePagination } from "@/hooks/usePagination";

export default function SessionRunsPage() {
  const { currentProject } = useProject();
  const pagination = usePagination();

  const [data, setData] = useState<PaginatedResponse<EvalRunResponse> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const result = await listSessionRuns({
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

  if (!currentProject) {
    return <EmptyState title="Select a project" description="Choose a project to view session evaluation runs." />;
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Session Evaluation Runs</h1>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchData} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No session evaluation runs" description="Create a session evaluation run to get started." />
      ) : (
        <>
          <EvalRunTable runs={data.items} />
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

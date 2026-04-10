"use client";

import { useQuery } from "@tanstack/react-query";
import { useProject } from "@/components/providers/ProjectProvider";
import { listSessionRuns } from "@/lib/api/evaluations";
import { EvalRunTable } from "@/components/features/EvalRunTable";
import { Pagination } from "@/components/common/Pagination";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { usePagination } from "@/hooks/usePagination";
import { queryKeys } from "@/lib/query/keys";

export default function SessionRunsPage() {
  const { currentProject } = useProject();
  const pagination = usePagination();
  const projectId = currentProject?.id ?? "";

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.evaluations.sessionRuns(projectId),
    queryFn: () => listSessionRuns({ limit: pagination.limit, offset: pagination.offset }),
    enabled: !!currentProject,
  });

  if (!currentProject) {
    return <EmptyState title="Select a project" description="Choose a project to view session evaluation runs." />;
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Session Evaluation Runs</h1>

      {isPending ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error instanceof Error ? error.message : "Failed to load runs"} onRetry={() => refetch()} />
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

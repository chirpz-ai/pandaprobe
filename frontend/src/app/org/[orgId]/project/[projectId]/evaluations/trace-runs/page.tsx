"use client";

import { useMemo, useState } from "react";
import {
  useQuery,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import { useProject } from "@/components/providers/ProjectProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useUrlState } from "@/hooks/useUrlState";
import { listTraceRuns } from "@/lib/api/evaluations";
import { EvalRunTable } from "@/components/features/EvalRunTable";
import { EvalRunDetailSidebar } from "@/components/features/EvalRunDetailSidebar";
import { EvalRunCreateSidebar } from "@/components/features/EvalRunCreateSidebar";
import { Pagination } from "@/components/common/Pagination";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/Button";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import { FlaskConical, X } from "lucide-react";
import { queryKeys } from "@/lib/query/keys";
import { EvaluationStatus } from "@/lib/api/enums";
import { extractErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";

const LIST_POLL_INTERVAL_MS = 5000;
const STATUS_ALL = "all";

const URL_CONFIG = {
  page: { default: "1" },
  limit: { default: "50" },
  status: { default: STATUS_ALL },
} as const;

export default function TraceRunsPage() {
  const { currentProject } = useProject();
  const queryClient = useQueryClient();
  const projectId = currentProject?.id ?? "";

  const { values, set, page, limit, offset, setPage, totalPages } =
    useUrlState(URL_CONFIG);

  useDocumentTitle("Trace Runs");

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const params = useMemo(() => {
    const p: Parameters<typeof listTraceRuns>[0] = { limit, offset };
    if (values.status !== STATUS_ALL) {
      p.status = values.status as EvaluationStatus;
    }
    return p;
  }, [limit, offset, values.status]);

  const { data, isPending, isPlaceholderData, error, refetch } = useQuery({
    queryKey: queryKeys.evaluations.traceRuns.list(
      projectId,
      params as unknown as Record<string, unknown>,
    ),
    queryFn: () => listTraceRuns(params),
    enabled: !!currentProject,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const anyPending = items.some(
        (r) =>
          r.status === EvaluationStatus.PENDING ||
          r.status === EvaluationStatus.RUNNING,
      );
      return anyPending ? LIST_POLL_INTERVAL_MS : false;
    },
    refetchIntervalInBackground: false,
  });

  const hasActiveFilters = values.status !== STATUS_ALL;

  function clearAllFilters() {
    set({ status: STATUS_ALL, page: "1" });
  }

  if (!currentProject) {
    return (
      <EmptyState
        title="Select a project"
        description="Choose a project to view trace evaluation runs."
      />
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-96px)] animate-fade-in">
      <div className="flex-shrink-0 space-y-3 pb-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-mono text-primary">
            Trace Evaluation Runs
          </h1>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setCreateOpen(true)}
          >
            <FlaskConical className="h-3.5 w-3.5 mr-1.5" />
            Create Evaluation
          </Button>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto">
          <Select
            value={values.status}
            onValueChange={(v) => set({ status: v, page: "1" })}
          >
            <SelectTrigger className="w-36 h-9 text-xs flex-shrink-0">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={STATUS_ALL}>All statuses</SelectItem>
              {Object.values(EvaluationStatus).map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="md"
              onClick={() => clearAllFilters()}
              className="text-xs text-warning hover:text-warning gap-1 flex-shrink-0"
            >
              <X className="h-3 w-3" />
              Clear
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        {isPending && !data ? (
          <LoadingState />
        ) : error && !data ? (
          <ErrorState
            message={extractErrorMessage(error)}
            onRetry={() => refetch()}
          />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            title="No evaluation runs"
            description={
              hasActiveFilters
                ? "Try adjusting your filters."
                : "Create an evaluation run to get started."
            }
          />
        ) : (
          <>
            <div
              className={cn(
                "flex-1 min-h-0 overflow-y-auto transition-opacity duration-200",
                isPlaceholderData && "opacity-60",
              )}
            >
              <EvalRunTable
                runs={data.items}
                onSelect={(run) => setSelectedRunId(run.id)}
              />
            </div>
            <Pagination
              page={page}
              totalPages={totalPages(data.total)}
              onPageChange={setPage}
              total={data.total}
              limit={limit}
              onLimitChange={(n) => set({ limit: String(n), page: "1" })}
            />
          </>
        )}
      </div>

      <EvalRunDetailSidebar
        mode="trace"
        open={selectedRunId !== null}
        runId={selectedRunId}
        onClose={() => setSelectedRunId(null)}
        onChanged={() =>
          queryClient.invalidateQueries({
            queryKey: queryKeys.evaluations.traceRuns.all(projectId),
          })
        }
      />

      <EvalRunCreateSidebar
        mode="trace"
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSubmitted={() =>
          queryClient.invalidateQueries({
            queryKey: queryKeys.evaluations.traceRuns.all(projectId),
          })
        }
      />
    </div>
  );
}

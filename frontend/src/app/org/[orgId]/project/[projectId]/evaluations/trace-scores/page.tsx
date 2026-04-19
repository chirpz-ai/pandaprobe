"use client";

import { useMemo, useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useProject } from "@/components/providers/ProjectProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useProjectPath } from "@/hooks/useNavigation";
import { useUrlState } from "@/hooks/useUrlState";
import {
  listTraceScores,
  getTraceMetrics,
  type ListTraceScoresParams,
} from "@/lib/api/evaluations";
import { queryKeys } from "@/lib/query/keys";
import { ScoreSource, ScoreStatus, ScoreDataType } from "@/lib/api/enums";
import { extractErrorMessage } from "@/lib/api/client";
import { ScoreListTable } from "@/components/features/ScoreListTable";
import { EvalRunDetailSidebar } from "@/components/features/EvalRunDetailSidebar";
import { Pagination } from "@/components/common/Pagination";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { DebouncedInput } from "@/components/common/DebouncedInput";
import { DateTimePicker } from "@/components/common/DateTimePicker";
import { Button } from "@/components/ui/Button";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import { X } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const ALL = "all";

const URL_CONFIG = {
  page: { default: "1" },
  limit: { default: "50" },
  name: { default: ALL },
  status: { default: ALL },
  source: { default: ALL },
  data_type: { default: ALL },
  environment: { default: "" },
  trace_id: { default: "" },
  eval_run_id: { default: "" },
  date_from: { default: "" },
  date_to: { default: "" },
} as const;

export default function TraceScoresPage() {
  const router = useRouter();
  const basePath = useProjectPath();
  const { currentProject } = useProject();
  const projectId = currentProject?.id ?? "";

  const { values, set, page, limit, offset, setPage, totalPages } =
    useUrlState(URL_CONFIG);

  useDocumentTitle("Trace Scores");

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const metricsQuery = useQuery({
    queryKey: ["trace-metrics"],
    queryFn: getTraceMetrics,
    staleTime: 5 * 60_000,
  });

  const params = useMemo<ListTraceScoresParams>(() => {
    const p: ListTraceScoresParams = { limit, offset };
    if (values.name !== ALL) p.name = values.name;
    if (values.status !== ALL) p.status = values.status;
    if (values.source !== ALL) p.source = values.source;
    if (values.data_type !== ALL) p.data_type = values.data_type;
    if (values.environment) p.environment = values.environment;
    if (values.trace_id) p.trace_id = values.trace_id;
    if (values.eval_run_id) p.eval_run_id = values.eval_run_id;
    if (values.date_from)
      p.date_from = new Date(values.date_from).toISOString();
    if (values.date_to) p.date_to = new Date(values.date_to).toISOString();
    return p;
  }, [
    limit,
    offset,
    values.name,
    values.status,
    values.source,
    values.data_type,
    values.environment,
    values.trace_id,
    values.eval_run_id,
    values.date_from,
    values.date_to,
  ]);

  const { data, isPending, isPlaceholderData, error, refetch } = useQuery({
    queryKey: queryKeys.evaluations.traceScores.list(
      projectId,
      params as unknown as Record<string, unknown>,
    ),
    queryFn: () => listTraceScores(params),
    enabled: !!currentProject,
    placeholderData: keepPreviousData,
  });

  const hasActiveFilters =
    values.name !== ALL ||
    values.status !== ALL ||
    values.source !== ALL ||
    values.data_type !== ALL ||
    values.environment !== "" ||
    values.trace_id !== "" ||
    values.eval_run_id !== "" ||
    values.date_from !== "" ||
    values.date_to !== "";

  function clearAllFilters() {
    set({
      name: ALL,
      status: ALL,
      source: ALL,
      data_type: ALL,
      environment: "",
      trace_id: "",
      eval_run_id: "",
      date_from: "",
      date_to: "",
      page: "1",
    });
  }

  function navigateToTrace(traceId: string) {
    router.push(`${basePath}/traces/${traceId}`);
  }

  if (!currentProject) {
    return (
      <EmptyState
        title="Select a project"
        description="Choose a project to view trace scores."
      />
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-96px)] animate-fade-in">
      <div className="flex-shrink-0 space-y-3 pb-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-mono text-primary">Trace Scores</h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={values.name}
            onValueChange={(v) => set({ name: v, page: "1" })}
          >
            <SelectTrigger className="w-40 h-9 text-xs flex-shrink-0">
              <SelectValue placeholder="Metric" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All metrics</SelectItem>
              {metricsQuery.data?.map((m) => (
                <SelectItem key={m.name} value={m.name}>
                  {m.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={values.status}
            onValueChange={(v) => set({ status: v, page: "1" })}
          >
            <SelectTrigger className="w-34 h-9 text-xs flex-shrink-0">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {Object.values(ScoreStatus).map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={values.source}
            onValueChange={(v) => set({ source: v, page: "1" })}
          >
            <SelectTrigger className="w-34 h-9 text-xs flex-shrink-0">
              <SelectValue placeholder="Source" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All sources</SelectItem>
              {Object.values(ScoreSource).map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={values.data_type}
            onValueChange={(v) => set({ data_type: v, page: "1" })}
          >
            <SelectTrigger className="w-36 h-9 text-xs flex-shrink-0">
              <SelectValue placeholder="Data type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All data types</SelectItem>
              {Object.values(ScoreDataType).map((d) => (
                <SelectItem key={d} value={d}>
                  {d}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <DebouncedInput
            value={values.environment}
            onChange={(v) => set({ environment: v, page: "1" })}
            placeholder="Environment"
            className="w-26 h-9 flex-shrink-0"
          />

          <DebouncedInput
            value={values.trace_id}
            onChange={(v) => set({ trace_id: v, page: "1" })}
            placeholder="Trace ID"
            className="w-22 h-9 flex-shrink-0"
          />

          <DebouncedInput
            value={values.eval_run_id}
            onChange={(v) => set({ eval_run_id: v, page: "1" })}
            placeholder="Eval run ID"
            className="w-28 h-9 flex-shrink-0"
          />

          <DateTimePicker
            value={values.date_from}
            onChange={(v) => set({ date_from: v, page: "1" })}
            placeholder="From"
            className="flex-shrink-0"
          />

          <DateTimePicker
            value={values.date_to}
            onChange={(v) => set({ date_to: v, page: "1" })}
            placeholder="Before"
            className="flex-shrink-0"
          />

          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="md"
              onClick={clearAllFilters}
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
            title="No scores"
            description={
              hasActiveFilters
                ? "Try adjusting your filters."
                : "Run an evaluation or annotate a trace to produce scores."
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
              <ScoreListTable
                mode="trace"
                scores={data.items}
                onNavigateTarget={navigateToTrace}
                onOpenRun={(runId) => setSelectedRunId(runId)}
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
        onChanged={() => refetch()}
      />
    </div>
  );
}

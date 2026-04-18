"use client";

import { useMemo, useState } from "react";
import {
  useQuery,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import { useProject } from "@/components/providers/ProjectProvider";
import { listSessions, type ListSessionsParams } from "@/lib/api/sessions";
import { queryKeys } from "@/lib/query/keys";
import { SessionTable } from "@/components/features/SessionTable";
import { RunEvalSidebar } from "@/components/features/RunEvalSidebar";
import { Pagination } from "@/components/common/Pagination";
import { SearchBar } from "@/components/common/SearchBar";
import { DebouncedInput } from "@/components/common/DebouncedInput";
import { DateTimePicker } from "@/components/common/DateTimePicker";
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
import { X, FlaskConical } from "lucide-react";
import { SessionSortBy, SortOrder } from "@/lib/api/enums";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useUrlState } from "@/hooks/useUrlState";
import { extractErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";

const URL_CONFIG = {
  page: { default: "1" },
  limit: { default: "50" },
  query: { default: "" },
  user_id: { default: "" },
  has_error: { default: "all" },
  tags: { default: "" },
  started_after: { default: "" },
  started_before: { default: "" },
  sortBy: { default: SessionSortBy.recent },
  sortOrder: { default: SortOrder.desc },
} as const;

export default function SessionsPage() {
  const { currentProject } = useProject();
  const queryClient = useQueryClient();
  const projectId = currentProject?.id ?? "";

  const { values, set, page, limit, offset, setPage, totalPages } =
    useUrlState(URL_CONFIG);

  useDocumentTitle("Sessions");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [runEvalOpen, setRunEvalOpen] = useState(false);

  const params = useMemo<ListSessionsParams>(() => {
    const p: ListSessionsParams = {
      limit,
      offset,
      sort_by: values.sortBy as ListSessionsParams["sort_by"],
      sort_order: values.sortOrder as ListSessionsParams["sort_order"],
    };
    if (values.query) p.query = values.query;
    if (values.user_id) p.user_id = values.user_id;
    if (values.has_error === "true") p.has_error = true;
    if (values.has_error === "false") p.has_error = false;
    if (values.tags) {
      const parsed = values.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      if (parsed.length > 0) p.tags = parsed;
    }
    if (values.started_after)
      p.started_after = new Date(values.started_after).toISOString();
    if (values.started_before)
      p.started_before = new Date(values.started_before).toISOString();
    return p;
  }, [
    limit,
    offset,
    values.sortBy,
    values.sortOrder,
    values.query,
    values.user_id,
    values.has_error,
    values.tags,
    values.started_after,
    values.started_before,
  ]);

  const { data, isPending, isPlaceholderData, error, refetch } = useQuery({
    queryKey: queryKeys.sessions.list(
      projectId,
      params as unknown as Record<string, unknown>,
    ),
    queryFn: () => listSessions(params),
    enabled: !!currentProject,
    placeholderData: keepPreviousData,
  });

  const hasActiveFilters =
    values.query !== "" ||
    values.user_id !== "" ||
    values.has_error !== "all" ||
    values.tags !== "" ||
    values.started_after !== "" ||
    values.started_before !== "";

  function clearAllFilters() {
    set({
      query: "",
      user_id: "",
      has_error: "all",
      tags: "",
      started_after: "",
      started_before: "",
      page: "1",
    });
  }

  if (!currentProject) {
    return (
      <EmptyState
        title="Select a project"
        description="Choose a project from the sidebar to view sessions."
      />
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-96px)] animate-fade-in">
      <div className="flex-shrink-0 space-y-3 pb-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-mono text-primary">Sessions</h1>
          <div className="flex items-center gap-2">
            {selected.size > 0 && (
              <span className="text-xs font-mono text-text-dim">
                {selected.size} selected
              </span>
            )}
            <Button
              variant="primary"
              size="sm"
              onClick={() => setRunEvalOpen(true)}
              disabled={selected.size === 0}
            >
              <FlaskConical className="h-3.5 w-3.5 mr-1.5" />
              Evaluate
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto">
          <SearchBar
            value={values.query}
            onChange={(v) => set({ query: v, page: "1" })}
            placeholder="Session ID"
            className="w-30 flex-shrink-0 text-xs"
          />
          <Select
            value={values.has_error}
            onValueChange={(v) => set({ has_error: v, page: "1" })}
          >
            <SelectTrigger className="w-28 h-9 text-xs flex-shrink-0">
              <SelectValue placeholder="Errors" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="true">Has errors</SelectItem>
              <SelectItem value="false">No errors</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={values.sortBy}
            onValueChange={(v) => set({ sortBy: v })}
          >
            <SelectTrigger className="w-32 h-9 text-xs flex-shrink-0">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              {Object.values(SessionSortBy).map((s) => (
                <SelectItem key={s} value={s}>
                  {s.replace("_", " ")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={values.sortOrder}
            onValueChange={(v) => set({ sortOrder: v })}
          >
            <SelectTrigger className="w-20 h-9 text-xs flex-shrink-0">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="asc">Asc</SelectItem>
              <SelectItem value="desc">Desc</SelectItem>
            </SelectContent>
          </Select>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <DateTimePicker
              value={values.started_after}
              onChange={(v) => set({ started_after: v, page: "1" })}
              placeholder="After..."
            />
          </div>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <DateTimePicker
              value={values.started_before}
              onChange={(v) => set({ started_before: v, page: "1" })}
              placeholder="Before..."
            />
          </div>
          <DebouncedInput
            value={values.tags}
            onChange={(v) => set({ tags: v, page: "1" })}
            placeholder="Tags"
            className="w-25"
          />
          <DebouncedInput
            value={values.user_id}
            onChange={(v) => set({ user_id: v, page: "1" })}
            placeholder="User ID"
            className="w-25"
          />
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
            title="No sessions found"
            description={
              hasActiveFilters
                ? "Try adjusting your filters."
                : "Sessions are automatically created when traces include a session_id."
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
              <SessionTable
                sessions={data.items}
                selected={selected}
                onSelectionChange={setSelected}
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

      <RunEvalSidebar
        mode="session"
        open={runEvalOpen}
        onClose={() => setRunEvalOpen(false)}
        targetIds={Array.from(selected)}
        onSubmitted={() =>
          queryClient.invalidateQueries({
            queryKey: queryKeys.evaluations.sessionRuns.all(projectId),
          })
        }
        onClearSelection={() => setSelected(new Set())}
      />
    </div>
  );
}

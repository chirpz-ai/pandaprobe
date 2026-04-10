"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useProject } from "@/components/providers/ProjectProvider";
import { listSessions, type ListSessionsParams } from "@/lib/api/sessions";
import { queryKeys } from "@/lib/query/keys";
import { SessionTable } from "@/components/features/SessionTable";
import { Pagination } from "@/components/common/Pagination";
import { SearchBar } from "@/components/common/SearchBar";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import { SessionSortBy, SortOrder } from "@/lib/api/enums";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useUrlState } from "@/hooks/useUrlState";
import { extractErrorMessage } from "@/lib/api/client";

const URL_CONFIG = {
  page: { default: "1" },
  query: { default: "" },
  sortBy: { default: SessionSortBy.recent },
  sortOrder: { default: SortOrder.desc },
} as const;

export default function SessionsPage() {
  const { currentProject } = useProject();
  const projectId = currentProject?.id ?? "";

  const { values, set, page, limit, offset, setPage, totalPages } =
    useUrlState(URL_CONFIG);

  useDocumentTitle("Sessions");

  const params = useMemo<ListSessionsParams>(() => ({
    limit,
    offset,
    sort_by: values.sortBy as ListSessionsParams["sort_by"],
    sort_order: values.sortOrder as ListSessionsParams["sort_order"],
    ...(values.query ? { query: values.query } : {}),
  }), [limit, offset, values.sortBy, values.sortOrder, values.query]);

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.sessions.list(projectId, params as unknown as Record<string, unknown>),
    queryFn: () => listSessions(params),
    enabled: !!currentProject,
  });

  if (!currentProject) {
    return (
      <EmptyState
        title="Select a project"
        description="Choose a project from the sidebar to view sessions."
      />
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Sessions</h1>

      <div className="flex flex-wrap items-center gap-3">
        <SearchBar
          value={values.query}
          onChange={(v) => set({ query: v, page: "1" })}
          placeholder="Search sessions..."
          className="w-64"
        />
        <Select value={values.sortBy} onValueChange={(v) => set({ sortBy: v })}>
          <SelectTrigger className="w-36">
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
        <Select value={values.sortOrder} onValueChange={(v) => set({ sortOrder: v })}>
          <SelectTrigger className="w-24">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="asc">Asc</SelectItem>
            <SelectItem value="desc">Desc</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isPending ? (
        <LoadingState />
      ) : error ? (
        <ErrorState
          message={extractErrorMessage(error)}
          onRetry={() => refetch()}
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="No sessions found"
          description="Sessions are automatically created when traces include a session_id."
        />
      ) : (
        <>
          <SessionTable sessions={data.items} />
          <Pagination
            page={page}
            totalPages={totalPages(data.total)}
            onPageChange={setPage}
            total={data.total}
          />
        </>
      )}
    </div>
  );
}

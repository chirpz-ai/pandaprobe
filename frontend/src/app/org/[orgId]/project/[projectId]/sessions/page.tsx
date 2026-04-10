"use client";

import { useState } from "react";
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
import { usePagination } from "@/hooks/usePagination";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import { SessionSortBy, SortOrder } from "@/lib/api/enums";

export default function SessionsPage() {
  const { currentProject } = useProject();
  const pagination = usePagination();

  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState<string>(SessionSortBy.recent);
  const [sortOrder, setSortOrder] = useState<string>(SortOrder.desc);

  const projectId = currentProject?.id ?? "";

  const params: ListSessionsParams = {
    limit: pagination.limit,
    offset: pagination.offset,
    sort_by: sortBy as ListSessionsParams["sort_by"],
    sort_order: sortOrder as ListSessionsParams["sort_order"],
    ...(query ? { query } : {}),
  };

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.sessions.list(projectId, params as Record<string, unknown>),
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
          value={query}
          onChange={(v) => {
            setQuery(v);
            pagination.reset();
          }}
          placeholder="Search sessions..."
          className="w-64"
        />
        <Select value={sortBy} onValueChange={setSortBy}>
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
        <Select value={sortOrder} onValueChange={setSortOrder}>
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
          message={error instanceof Error ? error.message : "Failed to load sessions"}
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

"use client";

import { useEffect, useState, useCallback } from "react";
import { useProject } from "@/components/providers/ProjectProvider";
import { listTraces, batchDeleteTraces, type ListTracesParams } from "@/lib/api/traces";
import type { TraceListItem, PaginatedResponse } from "@/lib/api/types";
import { TraceTable } from "@/components/features/TraceTable";
import { Pagination } from "@/components/common/Pagination";
import { SearchBar } from "@/components/common/SearchBar";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { usePagination } from "@/hooks/usePagination";
import { useToast } from "@/components/providers/ToastProvider";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import { TraceStatus, TraceSortBy, SortOrder } from "@/lib/api/enums";

export default function TracesPage() {
  const { currentProject } = useProject();
  const { toast } = useToast();
  const pagination = usePagination();

  const [data, setData] = useState<PaginatedResponse<TraceListItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [nameFilter, setNameFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<string>(TraceSortBy.started_at);
  const [sortOrder, setSortOrder] = useState<string>(SortOrder.desc);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);

  const fetchData = useCallback(async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const params: ListTracesParams = {
        limit: pagination.limit,
        offset: pagination.offset,
        sort_by: sortBy as ListTracesParams["sort_by"],
        sort_order: sortOrder as ListTracesParams["sort_order"],
      };
      if (nameFilter) params.name = nameFilter;
      if (statusFilter !== "all") params.status = statusFilter as ListTracesParams["status"];

      const result = await listTraces(params);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load traces");
    } finally {
      setLoading(false);
    }
  }, [currentProject, pagination.limit, pagination.offset, nameFilter, statusFilter, sortBy, sortOrder]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleBatchDelete() {
    if (selected.size === 0) return;
    try {
      await batchDeleteTraces({ trace_ids: Array.from(selected) });
      toast({ title: `Deleted ${selected.size} traces`, variant: "success" });
      setSelected(new Set());
      fetchData();
    } catch {
      toast({ title: "Failed to delete traces", variant: "error" });
    }
  }

  if (!currentProject) {
    return <EmptyState title="Select a project" description="Choose a project from the sidebar to view traces." />;
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-mono text-primary">Traces</h1>
        {selected.size > 0 && (
          <Button variant="destructive" size="sm" onClick={() => setConfirmDelete(true)}>
            Delete {selected.size} selected
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <SearchBar
          value={nameFilter}
          onChange={(v) => { setNameFilter(v); pagination.reset(); }}
          placeholder="Filter by name..."
          className="w-64"
        />
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); pagination.reset(); }}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {Object.values(TraceStatus).map((s) => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={sortBy} onValueChange={setSortBy}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            {Object.values(TraceSortBy).map((s) => (
              <SelectItem key={s} value={s}>{s.replace("_", " ")}</SelectItem>
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

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchData} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No traces found" description="Traces will appear here when your application sends them." />
      ) : (
        <>
          <TraceTable traces={data.items} />
          <Pagination
            page={pagination.page}
            totalPages={pagination.totalPages(data.total)}
            onPageChange={pagination.setPage}
            total={data.total}
          />
        </>
      )}

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete traces"
        description={`Are you sure you want to delete ${selected.size} trace(s)? This action cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={handleBatchDelete}
        destructive
      />
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useProject } from "@/components/providers/ProjectProvider";
import { listTraces, batchDeleteTraces, type ListTracesParams } from "@/lib/api/traces";
import { TraceTable } from "@/components/features/TraceTable";
import { Pagination } from "@/components/common/Pagination";
import { SearchBar } from "@/components/common/SearchBar";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
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
import { queryKeys } from "@/lib/query/keys";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useUrlState } from "@/hooks/useUrlState";
import { extractErrorMessage } from "@/lib/api/client";

const URL_CONFIG = {
  page: { default: "1" },
  name: { default: "" },
  status: { default: "all" },
  sortBy: { default: TraceSortBy.started_at },
  sortOrder: { default: SortOrder.desc },
} as const;

export default function TracesPage() {
  const { currentProject } = useProject();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const projectId = currentProject?.id ?? "";

  const { values, set, page, limit, offset, setPage, resetPage, totalPages } =
    useUrlState(URL_CONFIG);

  useDocumentTitle("Traces");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);

  const params = useMemo<ListTracesParams>(() => {
    const p: ListTracesParams = {
      limit,
      offset,
      sort_by: values.sortBy as ListTracesParams["sort_by"],
      sort_order: values.sortOrder as ListTracesParams["sort_order"],
    };
    if (values.name) p.name = values.name;
    if (values.status !== "all") p.status = values.status as ListTracesParams["status"];
    return p;
  }, [limit, offset, values.sortBy, values.sortOrder, values.name, values.status]);

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.traces.list(projectId, params as unknown as Record<string, unknown>),
    queryFn: () => listTraces(params),
    enabled: !!currentProject,
  });

  async function handleBatchDelete() {
    if (selected.size === 0) return;
    try {
      await batchDeleteTraces({ trace_ids: Array.from(selected) });
      toast({ title: `Deleted ${selected.size} traces`, variant: "success" });
      setSelected(new Set());
      queryClient.invalidateQueries({ queryKey: queryKeys.traces.all(projectId) });
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
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
          value={values.name}
          onChange={(v) => { set({ name: v, page: "1" }); }}
          placeholder="Filter by name..."
          className="w-64"
        />
        <Select value={values.status} onValueChange={(v) => { set({ status: v, page: "1" }); }}>
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
        <Select value={values.sortBy} onValueChange={(v) => set({ sortBy: v })}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            {Object.values(TraceSortBy).map((s) => (
              <SelectItem key={s} value={s}>{s.replace("_", " ")}</SelectItem>
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
        <ErrorState message={extractErrorMessage(error)} onRetry={() => refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No traces found" description="Traces will appear here when your application sends them." />
      ) : (
        <>
          <TraceTable traces={data.items} />
          <Pagination
            page={page}
            totalPages={totalPages(data.total)}
            onPageChange={setPage}
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

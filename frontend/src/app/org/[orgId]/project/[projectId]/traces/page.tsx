"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useProject } from "@/components/providers/ProjectProvider";
import {
  listTraces,
  batchDeleteTraces,
  batchUpdateTags,
  type ListTracesParams,
} from "@/lib/api/traces";
import { TraceTable } from "@/components/features/TraceTable";
import { Pagination } from "@/components/common/Pagination";
import { SearchBar } from "@/components/common/SearchBar";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { useToast } from "@/components/providers/ToastProvider";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import * as Dialog from "@radix-ui/react-dialog";
import { Trash2, Tag, X } from "lucide-react";
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

  const { values, set, page, limit, offset, setPage, totalPages } =
    useUrlState(URL_CONFIG);

  useDocumentTitle("Traces");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [showTagDialog, setShowTagDialog] = useState(false);
  const [tagInput, setTagInput] = useState("");

  const params = useMemo<ListTracesParams>(() => {
    const p: ListTracesParams = {
      limit,
      offset,
      sort_by: values.sortBy as ListTracesParams["sort_by"],
      sort_order: values.sortOrder as ListTracesParams["sort_order"],
    };
    if (values.name) p.name = values.name;
    if (values.status !== "all")
      p.status = values.status as ListTracesParams["status"];
    return p;
  }, [
    limit,
    offset,
    values.sortBy,
    values.sortOrder,
    values.name,
    values.status,
  ]);

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.traces.list(
      projectId,
      params as unknown as Record<string, unknown>,
    ),
    queryFn: () => listTraces(params),
    enabled: !!currentProject,
  });

  async function handleBatchDelete() {
    if (selected.size === 0) return;
    try {
      await batchDeleteTraces({ trace_ids: Array.from(selected) });
      toast({ title: `Deleted ${selected.size} traces`, variant: "success" });
      setSelected(new Set());
      queryClient.invalidateQueries({
        queryKey: queryKeys.traces.all(projectId),
      });
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  async function handleBatchTag() {
    const tags = tagInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    if (selected.size === 0 || tags.length === 0) return;
    try {
      await batchUpdateTags({ trace_ids: Array.from(selected), add_tags: tags });
      toast({
        title: `Added ${tags.length} tag(s) to ${selected.size} trace(s)`,
        variant: "success",
      });
      setSelected(new Set());
      setTagInput("");
      setShowTagDialog(false);
      queryClient.invalidateQueries({
        queryKey: queryKeys.traces.all(projectId),
      });
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  if (!currentProject) {
    return (
      <EmptyState
        title="Select a project"
        description="Choose a project from the sidebar to view traces."
      />
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-mono text-primary">Traces</h1>
        {selected.size > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-text-dim">
              {selected.size} selected
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowTagDialog(true)}
            >
              <Tag className="h-3.5 w-3.5 mr-1.5" />
              Tag
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 className="h-3.5 w-3.5 mr-1.5" />
              Delete
            </Button>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <SearchBar
          value={values.name}
          onChange={(v) => {
            set({ name: v, page: "1" });
          }}
          placeholder="Filter by name..."
          className="w-64"
        />
        <Select
          value={values.status}
          onValueChange={(v) => {
            set({ status: v, page: "1" });
          }}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {Object.values(TraceStatus).map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={values.sortBy} onValueChange={(v) => set({ sortBy: v })}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            {Object.values(TraceSortBy).map((s) => (
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
          title="No traces found"
          description="Traces will appear here when your application sends them."
        />
      ) : (
        <>
          <TraceTable
            traces={data.items}
            selected={selected}
            onSelectionChange={setSelected}
          />
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

      <Dialog.Root
        open={showTagDialog}
        onOpenChange={(open) => {
          setShowTagDialog(open);
          if (!open) setTagInput("");
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 border border-border bg-surface p-6 animate-fade-in">
            <div className="flex items-start justify-between mb-4">
              <Dialog.Title className="text-sm font-mono text-primary">
                Add tags to {selected.size} trace(s)
              </Dialog.Title>
              <Dialog.Close className="text-text-muted hover:text-text transition-colors">
                <X className="h-4 w-4" />
              </Dialog.Close>
            </div>
            <Dialog.Description className="text-xs text-text-dim mb-4">
              Enter one or more tags separated by commas.
            </Dialog.Description>
            <Input
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              placeholder="e.g. production, v2, reviewed"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleBatchTag();
              }}
            />
            <div className="flex justify-end gap-2 mt-6">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setShowTagDialog(false);
                  setTagInput("");
                }}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleBatchTag}
                disabled={tagInput.trim().length === 0}
              >
                Add Tags
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}

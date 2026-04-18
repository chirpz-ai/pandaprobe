"use client";

import { useMemo, useState } from "react";
import {
  useQuery,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import { useProject } from "@/components/providers/ProjectProvider";
import {
  listTraces,
  batchDeleteTraces,
  batchUpdateTags,
  type ListTracesParams,
} from "@/lib/api/traces";
import { TraceTable } from "@/components/features/TraceTable";
import { EvaluationSidebar } from "@/components/features/EvaluationSidebar";
import { Pagination } from "@/components/common/Pagination";
import { SearchBar } from "@/components/common/SearchBar";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { useToast } from "@/components/providers/ToastProvider";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { DebouncedInput } from "@/components/common/DebouncedInput";
import { DateTimePicker } from "@/components/common/DateTimePicker";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import * as Dialog from "@radix-ui/react-dialog";
import { Trash2, Tag, X, FlaskConical } from "lucide-react";
import { TraceStatus, TraceSortBy, SortOrder } from "@/lib/api/enums";
import { queryKeys } from "@/lib/query/keys";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useUrlState } from "@/hooks/useUrlState";
import { extractErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";

const URL_CONFIG = {
  page: { default: "1" },
  limit: { default: "50" },
  name: { default: "" },
  status: { default: "all" },
  session_id: { default: "" },
  user_id: { default: "" },
  tags: { default: "" },
  started_after: { default: "" },
  started_before: { default: "" },
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
  const [runEvalOpen, setRunEvalOpen] = useState(false);
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
    if (values.session_id) p.session_id = values.session_id;
    if (values.user_id) p.user_id = values.user_id;
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
    values.name,
    values.status,
    values.session_id,
    values.user_id,
    values.tags,
    values.started_after,
    values.started_before,
  ]);

  const { data, isPending, isPlaceholderData, error, refetch } = useQuery({
    queryKey: queryKeys.traces.list(
      projectId,
      params as unknown as Record<string, unknown>,
    ),
    queryFn: () => listTraces(params),
    enabled: !!currentProject,
    placeholderData: keepPreviousData,
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
      await batchUpdateTags({
        trace_ids: Array.from(selected),
        add_tags: tags,
      });
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

  const hasActiveFilters =
    values.name !== "" ||
    values.status !== "all" ||
    values.session_id !== "" ||
    values.user_id !== "" ||
    values.tags !== "" ||
    values.started_after !== "" ||
    values.started_before !== "";

  function clearAllFilters() {
    set({
      name: "",
      status: "all",
      session_id: "",
      user_id: "",
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
        description="Choose a project from the sidebar to view traces."
      />
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-96px)] animate-fade-in">
      {/* Fixed header */}
      <div className="flex-shrink-0 space-y-3 pb-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-mono text-primary">Traces</h1>
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
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowTagDialog(true)}
              disabled={selected.size === 0}
            >
              <Tag className="h-3.5 w-3.5 mr-1.5" />
              Tag
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setConfirmDelete(true)}
              disabled={selected.size === 0}
            >
              <Trash2 className="h-3.5 w-3.5 mr-1.5" />
              Delete
            </Button>
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-2 overflow-x-auto">
          <SearchBar
            value={values.name}
            onChange={(v) => set({ name: v, page: "1" })}
            placeholder="Name"
            className="w-30 flex-shrink-0 text-xs"
          />
          <Select
            value={values.status}
            onValueChange={(v) => set({ status: v, page: "1" })}
          >
            <SelectTrigger className="w-30 h-9 text-xs flex-shrink-0">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              {Object.values(TraceStatus).map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
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
            value={values.session_id}
            onChange={(v) => set({ session_id: v, page: "1" })}
            placeholder="Session ID"
            className="w-25"
          />
          <DebouncedInput
            value={values.user_id}
            onChange={(v) => set({ user_id: v, page: "1" })}
            placeholder="User ID"
            className="w-20"
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

      {/* Scrollable table area */}
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
            title="No traces found"
            description={
              hasActiveFilters
                ? "Try adjusting your filters."
                : "Traces will appear here when your application sends them."
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
              <TraceTable
                traces={data.items}
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

      <EvaluationSidebar
        mode="trace"
        open={runEvalOpen}
        onClose={() => setRunEvalOpen(false)}
        targetIds={Array.from(selected)}
        onSubmitted={() =>
          queryClient.invalidateQueries({
            queryKey: queryKeys.evaluations.traceRuns.all(projectId),
          })
        }
        onClearSelection={() => setSelected(new Set())}
      />
    </div>
  );
}

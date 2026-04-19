"use client";

import { useMemo, useState, useEffect } from "react";
import { useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import {
  X,
  RefreshCw,
  Pause,
  Play,
  Zap,
  Trash2,
  SquarePen,
  Clock,
  Filter,
  Loader2,
  Copy,
  Check,
  ArrowRight,
  Eye,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  getMonitor,
  deleteMonitor,
  pauseMonitor,
  resumeMonitor,
  triggerMonitor,
} from "@/lib/api/evaluations";
import type { MonitorResponse } from "@/lib/api/types";
import { MonitorStatus } from "@/lib/api/enums";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Tooltip } from "@/components/ui/Tooltip";
import { formatDateTime, formatRelativeTime } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";
import { useToast } from "@/components/providers/ToastProvider";
import { useEvalRunTracker } from "@/components/providers/EvalRunTrackerProvider";
import { extractErrorMessage } from "@/lib/api/client";
import { queryKeys } from "@/lib/query/keys";
import { EvalRunDetailSidebar } from "./EvalRunDetailSidebar";

/** Poll detail page only when the next firing time is near (~2 minutes). */
const IMMINENT_WINDOW_MS = 2 * 60 * 1000;
const POLL_INTERVAL_MS = 5000;

interface MonitorDetailSidebarProps {
  monitorId: string | null;
  projectId: string;
  orgId: string;
  open: boolean;
  onClose: () => void;
  /** Called when the user clicks Edit. Parent should open MonitorFormSidebar with this monitor. */
  onEdit?: (monitor: MonitorResponse) => void;
  /** Called after a delete/pause/resume/trigger so the caller can invalidate its own queries. */
  onChanged?: () => void;
}

/**
 * Sidebar surface for drilling into a single monitor: shows summary, filters,
 * metrics, and exposes Edit / Pause|Resume / Trigger / Delete actions.
 * Provides a "View runs" button that navigates to the monitor's dedicated
 * runs sub-page, and an inline "View last run" quick inspect.
 */
export function MonitorDetailSidebar({
  monitorId,
  projectId,
  orgId,
  open,
  onClose,
  onEdit,
  onChanged,
}: MonitorDetailSidebarProps) {
  const router = useRouter();
  const { toast } = useToast();
  const tracker = useEvalRunTracker();
  const queryClient = useQueryClient();

  const [actionPending, setActionPending] = useState<
    "pause" | "resume" | "trigger" | "delete" | null
  >(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const [lastRunSidebarOpen, setLastRunSidebarOpen] = useState(false);

  const enabled = open && !!monitorId;

  useEffect(() => {
    setCopiedId(false);
    setLastRunSidebarOpen(false);
  }, [monitorId, open]);

  const monitorQuery = useQuery<MonitorResponse>({
    queryKey: queryKeys.evaluations.monitors.detail(monitorId ?? ""),
    queryFn: () => getMonitor(monitorId!),
    enabled,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const m = query.state.data;
      if (!m) return false;
      if (m.status !== MonitorStatus.ACTIVE) return false;
      if (!m.next_run_at) return false;
      const diff = new Date(m.next_run_at).getTime() - Date.now();
      if (diff > 0 && diff < IMMINENT_WINDOW_MS) return POLL_INTERVAL_MS;
      return false;
    },
    refetchIntervalInBackground: false,
  });

  const monitor = monitorQuery.data ?? null;

  const filtersList = useMemo<Array<[string, string]>>(() => {
    if (!monitor || !monitor.filters) return [];
    return Object.entries(monitor.filters)
      .filter(([, v]) => v !== null && v !== undefined && v !== "")
      .map(([k, v]) => [k, formatFilterValue(v)]);
  }, [monitor]);

  function notifyChanged(): Promise<unknown> {
    const invalidations: Promise<unknown>[] = [
      queryClient.invalidateQueries({
        queryKey: queryKeys.evaluations.monitors.all(projectId),
      }),
    ];
    if (monitorId) {
      invalidations.push(
        queryClient.invalidateQueries({
          queryKey: queryKeys.evaluations.monitors.detail(monitorId),
        }),
      );
    }
    onChanged?.();
    return Promise.all(invalidations);
  }

  function handleCopyId() {
    if (!monitor) return;
    navigator.clipboard.writeText(monitor.id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  }

  async function handlePause() {
    if (!monitor) return;
    setActionPending("pause");
    try {
      await pauseMonitor(monitor.id);
      toast({ title: "Monitor paused", variant: "success" });
      await notifyChanged();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setActionPending(null);
    }
  }

  async function handleResume() {
    if (!monitor) return;
    setActionPending("resume");
    try {
      await resumeMonitor(monitor.id);
      toast({ title: "Monitor resumed", variant: "success" });
      await notifyChanged();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setActionPending(null);
    }
  }

  async function handleTrigger() {
    if (!monitor) return;
    setActionPending("trigger");
    try {
      const run = await triggerMonitor(monitor.id);
      tracker?.register({
        runId: run.id,
        mode: monitor.target_type === "SESSION" ? "session" : "trace",
        targetIds: [],
      });
      toast({
        title: "Run queued",
        description: "A new run has been kicked off for this monitor.",
        variant: "success",
      });
      await Promise.all([
        notifyChanged(),
        queryClient.invalidateQueries({
          queryKey: queryKeys.evaluations.monitors.runs(monitor.id, {}),
        }),
        queryClient.invalidateQueries({
          queryKey: [
            monitor.target_type === "SESSION" ? "sessionRuns" : "traceRuns",
          ],
        }),
      ]);
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setActionPending(null);
    }
  }

  async function handleDelete() {
    if (!monitor) return;
    setActionPending("delete");
    try {
      await deleteMonitor(monitor.id);
      toast({ title: "Monitor deleted", variant: "success" });
      await notifyChanged();
      onClose();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setActionPending(null);
      setConfirmDelete(false);
    }
  }

  const title = monitor?.name || (monitor ? `Monitor ${monitor.id.slice(0, 8)}` : "Monitor");
  const isRefreshing = monitorQuery.isFetching;
  const isActive = monitor?.status === MonitorStatus.ACTIVE;
  const targetMode: "trace" | "session" =
    monitor?.target_type === "SESSION" ? "session" : "trace";

  const lastRunSidebarRunId = lastRunSidebarOpen ? monitor?.last_run_id ?? null : null;

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-bg/50" onClick={onClose} />
      )}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-[560px] max-w-[92vw] bg-surface border-l border-border",
          "flex flex-col transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between h-12 px-4 border-b border-border flex-shrink-0 gap-2">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider truncate">
            {title}
          </h2>
          <div className="flex items-center gap-1 flex-shrink-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => monitorQuery.refetch()}
              disabled={!monitorId || isRefreshing}
              aria-label="Refresh"
              title="Refresh"
            >
              <RefreshCw
                className={cn("h-3.5 w-3.5", isRefreshing && "animate-spin")}
              />
            </Button>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          {!monitorId ? null : monitorQuery.isPending && !monitor ? (
            <div className="flex items-center justify-center h-24 text-xs text-text-muted font-mono">
              Loading monitor…
            </div>
          ) : monitorQuery.error ? (
            <div className="p-4 text-xs font-mono text-error">
              {extractErrorMessage(monitorQuery.error)}
            </div>
          ) : !monitor ? null : (
            <>
              <div className="px-4 py-3 border-b border-border space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <StatusBadge status={monitor.status} />
                  <Badge variant="default">{monitor.target_type}</Badge>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <KVRow label="Cadence">
                    <span className="text-text truncate">
                      {formatCadence(monitor.cadence)}
                    </span>
                  </KVRow>
                  <KVRow label="Sampling">
                    <span className="text-text">
                      {formatSamplingRate(monitor.sampling_rate)}
                    </span>
                  </KVRow>
                  <KVRow label="Model">
                    <span className="text-text truncate">
                      {monitor.model ?? (
                        <span className="text-text-muted">default</span>
                      )}
                    </span>
                  </KVRow>
                  <KVRow label="Only if changed">
                    <span className="text-text">
                      {monitor.only_if_changed ? "Yes" : "No"}
                    </span>
                  </KVRow>
                  <KVRow label="Last run">
                    <span className="text-text flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" />
                      {monitor.last_run_at ? (
                        formatRelativeTime(monitor.last_run_at)
                      ) : (
                        <span className="text-text-muted">—</span>
                      )}
                    </span>
                  </KVRow>
                  <KVRow label="Next run">
                    <span className="text-text flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" />
                      {monitor.next_run_at ? (
                        formatRelativeTime(monitor.next_run_at)
                      ) : (
                        <span className="text-text-muted">—</span>
                      )}
                    </span>
                  </KVRow>
                  <KVRow label="Created">
                    <span className="text-text flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" />
                      {formatDateTime(monitor.created_at)}
                    </span>
                  </KVRow>
                  <KVRow label="Updated">
                    <span className="text-text flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" />
                      {formatDateTime(monitor.updated_at)}
                    </span>
                  </KVRow>
                  <KVRow label="Monitor ID" truncate={false}>
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span
                        className="text-text-dim truncate min-w-0"
                        title={monitor.id}
                      >
                        {monitor.id}
                      </span>
                      <Tooltip content={copiedId ? "Copied!" : "Copy monitor ID"}>
                        <button
                          className="text-text-muted hover:text-text transition-colors flex-shrink-0"
                          onClick={handleCopyId}
                          aria-label="Copy monitor ID"
                        >
                          {copiedId ? (
                            <Check className="h-3 w-3 text-success" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </button>
                      </Tooltip>
                    </div>
                  </KVRow>
                </div>
              </div>

              <div className="px-4 py-3 border-b border-border">
                <label className="block text-[10px] font-mono text-text-muted uppercase tracking-wider mb-1.5">
                  Metrics
                </label>
                <div className="flex gap-1 flex-wrap">
                  {monitor.metric_names.length === 0 ? (
                    <span className="text-[11px] font-mono text-text-muted">
                      None
                    </span>
                  ) : (
                    monitor.metric_names.map((m) => (
                      <Badge key={m} variant="info">
                        {m}
                      </Badge>
                    ))
                  )}
                </div>
              </div>

              {filtersList.length > 0 && (
                <div className="px-4 py-3 border-b border-border">
                  <label className="flex items-center gap-1 text-[10px] font-mono text-text-muted uppercase tracking-wider mb-1.5">
                    <Filter className="h-2.5 w-2.5" />
                    Filters
                  </label>
                  <div className="border border-border/40">
                    <table className="text-[11px] font-mono w-full border-collapse">
                      <tbody>
                        {filtersList.map(([key, val]) => (
                          <tr
                            key={key}
                            className="border-b border-border/40 last:border-0"
                          >
                            <td className="text-text-muted px-2 py-0.5 whitespace-nowrap align-top border-r border-border/40">
                              {key}
                            </td>
                            <td className="text-text px-2 py-0.5 break-all">
                              {val}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="px-4 py-3 border-b border-border flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onEdit?.(monitor)}
                  disabled={actionPending !== null}
                >
                  <SquarePen className="h-3 w-3" />
                  Edit
                </Button>
                {isActive ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handlePause}
                    disabled={actionPending !== null}
                  >
                    {actionPending === "pause" ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Pause className="h-3 w-3" />
                    )}
                    Pause
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleResume}
                    disabled={actionPending !== null}
                  >
                    {actionPending === "resume" ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Play className="h-3 w-3" />
                    )}
                    Resume
                  </Button>
                )}
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleTrigger}
                  disabled={actionPending !== null}
                >
                  {actionPending === "trigger" ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Zap className="h-3 w-3" />
                  )}
                  Trigger
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setConfirmDelete(true)}
                  disabled={actionPending !== null}
                >
                  {actionPending === "delete" ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Trash2 className="h-3 w-3" />
                  )}
                  Delete
                </Button>
              </div>

              <div className="px-4 py-3 border-b border-border space-y-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    router.push(
                      `/org/${orgId}/project/${projectId}/evaluations/monitors/${monitor.id}`,
                    );
                    onClose();
                  }}
                  className="w-full justify-between"
                >
                  <span className="flex items-center gap-1.5">
                    View runs
                  </span>
                  <ArrowRight className="h-3 w-3" />
                </Button>
                {monitor.last_run_id && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setLastRunSidebarOpen(true)}
                    className="w-full justify-start"
                  >
                    <Eye className="h-3 w-3" />
                    View last run
                  </Button>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      <EvalRunDetailSidebar
        mode={targetMode}
        runId={lastRunSidebarRunId}
        open={lastRunSidebarOpen}
        onClose={() => setLastRunSidebarOpen(false)}
        onChanged={() => {
          notifyChanged();
        }}
      />

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={(v) => {
          if (!v && actionPending === "delete") return;
          setConfirmDelete(v);
        }}
        title="Delete monitor"
        description="Delete this monitor? The monitor stops firing and its existing runs are preserved. This action cannot be undone."
        confirmLabel="Delete"
        onConfirm={handleDelete}
        destructive
      />
    </>
  );
}

function KVRow({
  label,
  children,
  truncate = true,
}: {
  label: string;
  children: React.ReactNode;
  truncate?: boolean;
}) {
  return (
    <div className="min-w-0">
      <span className="text-[10px] text-text-muted uppercase tracking-wider block">
        {label}
      </span>
      <div className={truncate ? "truncate" : "min-w-0"}>{children}</div>
    </div>
  );
}

function formatSamplingRate(rate: number): string {
  if (rate == null || Number.isNaN(rate)) return "—";
  if (rate >= 1) return "100%";
  return `${Math.round(rate * 100)}%`;
}

function formatCadence(cadence: string): string {
  if (!cadence) return "—";
  if (cadence.startsWith("cron:")) {
    return `cron: ${cadence.slice("cron:".length).trim()}`;
  }
  switch (cadence) {
    case "every_6h":
      return "every 6h";
    case "daily":
      return "daily";
    case "weekly":
      return "weekly";
    default:
      return cadence;
  }
}

function formatFilterValue(value: unknown): string {
  if (value == null) return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

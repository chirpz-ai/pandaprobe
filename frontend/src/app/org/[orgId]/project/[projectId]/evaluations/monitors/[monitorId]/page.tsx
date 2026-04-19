"use client";

import { useMemo, useState } from "react";
import {
  useQuery,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  SquarePen,
  Pause,
  Play,
  Zap,
  Trash2,
  Clock,
  Filter,
  Copy,
  Check,
  Loader2,
  Radio,
} from "lucide-react";
import { useProject } from "@/components/providers/ProjectProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useUrlState } from "@/hooks/useUrlState";
import {
  getMonitor,
  getMonitorRuns,
  deleteMonitor,
  pauseMonitor,
  resumeMonitor,
  triggerMonitor,
} from "@/lib/api/evaluations";
import type { MonitorResponse } from "@/lib/api/types";
import { MonitorStatus, EvaluationStatus } from "@/lib/api/enums";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Tooltip } from "@/components/ui/Tooltip";
import { Pagination } from "@/components/common/Pagination";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { EvalRunTable } from "@/components/features/EvalRunTable";
import { EvalRunDetailSidebar } from "@/components/features/EvalRunDetailSidebar";
import { MonitorFormSidebar } from "@/components/features/MonitorFormSidebar";
import { formatDateTime, formatRelativeTime } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";
import { useToast } from "@/components/providers/ToastProvider";
import { useEvalRunTracker } from "@/components/providers/EvalRunTrackerProvider";
import { extractErrorMessage } from "@/lib/api/client";
import { queryKeys } from "@/lib/query/keys";

const RUNS_POLL_INTERVAL_MS = 5000;
const DETAIL_POLL_INTERVAL_MS = 5000;
const IMMINENT_WINDOW_MS = 2 * 60 * 1000;

const URL_CONFIG = {
  page: { default: "1" },
  limit: { default: "50" },
} as const;

export default function MonitorDetailPage() {
  const routeParams = useParams<{
    orgId: string;
    projectId: string;
    monitorId: string;
  }>();
  const { orgId, projectId: projectIdFromUrl, monitorId } = routeParams;
  const { currentProject } = useProject();
  const queryClient = useQueryClient();
  const router = useRouter();
  const { toast } = useToast();
  const tracker = useEvalRunTracker();
  const projectId = currentProject?.id ?? projectIdFromUrl ?? "";
  const monitorsListHref = `/org/${orgId}/project/${projectId}/evaluations/monitors`;

  const { page, limit, offset, setPage, set, totalPages } =
    useUrlState(URL_CONFIG);

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [actionPending, setActionPending] = useState<
    "pause" | "resume" | "trigger" | "delete" | null
  >(null);
  const [copiedId, setCopiedId] = useState(false);

  const monitorQuery = useQuery<MonitorResponse>({
    queryKey: queryKeys.evaluations.monitors.detail(monitorId),
    queryFn: () => getMonitor(monitorId),
    enabled: !!monitorId,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const m = query.state.data;
      if (!m) return false;
      if (m.status !== MonitorStatus.ACTIVE) return false;
      if (!m.next_run_at) return false;
      const diff = new Date(m.next_run_at).getTime() - Date.now();
      if (diff > 0 && diff < IMMINENT_WINDOW_MS) return DETAIL_POLL_INTERVAL_MS;
      return false;
    },
    refetchIntervalInBackground: false,
  });

  const runsParams = useMemo(() => ({ limit, offset }), [limit, offset]);

  const runsQuery = useQuery({
    queryKey: queryKeys.evaluations.monitors.runs(
      monitorId,
      runsParams as unknown as Record<string, unknown>,
    ),
    queryFn: () => getMonitorRuns(monitorId, runsParams),
    enabled: !!monitorId,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const anyPending = items.some(
        (r) =>
          r.status === EvaluationStatus.PENDING ||
          r.status === EvaluationStatus.RUNNING,
      );
      return anyPending ? RUNS_POLL_INTERVAL_MS : false;
    },
    refetchIntervalInBackground: false,
  });

  const monitor = monitorQuery.data ?? null;
  const isActive = monitor?.status === MonitorStatus.ACTIVE;
  const targetMode: "trace" | "session" =
    monitor?.target_type === "SESSION" ? "session" : "trace";

  useDocumentTitle(monitor?.name ? `${monitor.name} · Runs` : "Monitor");

  const filtersList = useMemo<Array<[string, string]>>(() => {
    if (!monitor || !monitor.filters) return [];
    return Object.entries(monitor.filters)
      .filter(([, v]) => v !== null && v !== undefined && v !== "")
      .map(([k, v]) => [k, formatFilterValue(v)]);
  }, [monitor]);

  function invalidateAll() {
    queryClient.invalidateQueries({
      queryKey: queryKeys.evaluations.monitors.all(projectId),
    });
    queryClient.invalidateQueries({
      queryKey: queryKeys.evaluations.monitors.detail(monitorId),
    });
    queryClient.invalidateQueries({
      queryKey: queryKeys.evaluations.monitors.runs(monitorId, {}),
    });
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
      invalidateAll();
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
      invalidateAll();
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
        mode: targetMode,
        targetIds: [],
      });
      toast({
        title: "Run queued",
        description: "A new run has been kicked off for this monitor.",
        variant: "success",
      });
      invalidateAll();
      queryClient.invalidateQueries({
        queryKey: [targetMode === "session" ? "sessionRuns" : "traceRuns"],
      });
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
      queryClient.invalidateQueries({
        queryKey: queryKeys.evaluations.monitors.all(projectId),
      });
      router.push(monitorsListHref);
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setActionPending(null);
      setConfirmDelete(false);
    }
  }

  if (monitorQuery.isPending && !monitor) {
    return <LoadingState />;
  }

  if (monitorQuery.error && !monitor) {
    return (
      <ErrorState
        message={extractErrorMessage(monitorQuery.error)}
        onRetry={() => monitorQuery.refetch()}
      />
    );
  }

  if (!monitor) {
    return (
      <EmptyState
        title="Monitor not found"
        description="This monitor may have been deleted."
      />
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-96px)] animate-fade-in">
      <div className="flex-shrink-0 pb-3">
        <Link
          href={monitorsListHref}
          className="inline-flex items-center gap-1 text-[11px] font-mono text-text-muted hover:text-text transition-colors mb-2"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to monitors
        </Link>

        <div className="border border-border bg-surface">
          <div className="px-4 py-3 border-b border-border flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Radio className="h-3.5 w-3.5 text-text-muted flex-shrink-0" />
                <h1 className="text-base font-mono text-text truncate">
                  {monitor.name}
                </h1>
                <StatusBadge status={monitor.status} />
                <Badge variant="default">{monitor.target_type}</Badge>
              </div>
              <div className="flex items-center gap-1.5 min-w-0">
                <span
                  className="text-[11px] font-mono text-text-dim truncate min-w-0"
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
            </div>
            <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setFormOpen(true)}
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
          </div>

          <div className="px-4 py-3 grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-2 text-xs font-mono">
            <SummaryCell
              label="Cadence"
              value={formatCadence(monitor.cadence)}
            />
            <SummaryCell
              label="Sampling"
              value={formatSamplingRate(monitor.sampling_rate)}
            />
            <SummaryCell
              label="Model"
              value={monitor.model ?? "default"}
              dim={!monitor.model}
            />
            <SummaryCell
              label="Only if changed"
              value={monitor.only_if_changed ? "Yes" : "No"}
            />
            <SummaryCell
              label="Last run"
              value={
                monitor.last_run_at
                  ? formatRelativeTime(monitor.last_run_at)
                  : "—"
              }
              icon={<Clock className="h-2.5 w-2.5" />}
            />
            <SummaryCell
              label="Next run"
              value={
                monitor.next_run_at
                  ? formatRelativeTime(monitor.next_run_at)
                  : "—"
              }
              icon={<Clock className="h-2.5 w-2.5" />}
            />
            <SummaryCell
              label="Created"
              value={formatDateTime(monitor.created_at)}
              icon={<Clock className="h-2.5 w-2.5" />}
            />
            <SummaryCell
              label="Updated"
              value={formatDateTime(monitor.updated_at)}
              icon={<Clock className="h-2.5 w-2.5" />}
            />
          </div>

          <div className="px-4 py-3 border-t border-border">
            <span className="block text-[10px] font-mono text-text-muted uppercase tracking-wider mb-1.5">
              Metrics
            </span>
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
            <div className="px-4 py-3 border-t border-border">
              <span className="flex items-center gap-1 text-[10px] font-mono text-text-muted uppercase tracking-wider mb-1.5">
                <Filter className="h-2.5 w-2.5" />
                Filters
              </span>
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
        </div>

        <h2 className="text-sm font-mono text-text-muted uppercase tracking-wider mt-4 mb-2">
          Runs
          {runsQuery.data && (
            <span className="ml-2 text-text-dim normal-case tracking-normal">
              · {runsQuery.data.total}
            </span>
          )}
        </h2>
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        {runsQuery.isPending && !runsQuery.data ? (
          <LoadingState />
        ) : runsQuery.error && !runsQuery.data ? (
          <ErrorState
            message={extractErrorMessage(runsQuery.error)}
            onRetry={() => runsQuery.refetch()}
          />
        ) : !runsQuery.data || runsQuery.data.items.length === 0 ? (
          <EmptyState
            title="No runs yet"
            description="Runs will appear here once the monitor has fired at least once."
          />
        ) : (
          <>
            <div
              className={cn(
                "flex-1 min-h-0 overflow-y-auto transition-opacity duration-200",
                runsQuery.isPlaceholderData && "opacity-60",
              )}
            >
              <EvalRunTable
                runs={runsQuery.data.items}
                onSelect={(run) => setSelectedRunId(run.id)}
              />
            </div>
            <Pagination
              page={page}
              totalPages={totalPages(runsQuery.data.total)}
              onPageChange={setPage}
              total={runsQuery.data.total}
              limit={limit}
              onLimitChange={(n) => set({ limit: String(n), page: "1" })}
            />
          </>
        )}
      </div>

      <EvalRunDetailSidebar
        mode={targetMode}
        runId={selectedRunId}
        open={selectedRunId !== null}
        onClose={() => setSelectedRunId(null)}
        onChanged={() =>
          queryClient.invalidateQueries({
            queryKey: queryKeys.evaluations.monitors.runs(monitorId, {}),
          })
        }
      />

      <MonitorFormSidebar
        monitor={monitor}
        projectId={projectId}
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSubmitted={invalidateAll}
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
    </div>
  );
}

function SummaryCell({
  label,
  value,
  icon,
  dim,
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
  dim?: boolean;
}) {
  return (
    <div className="min-w-0">
      <span className="block text-[10px] text-text-muted uppercase tracking-wider">
        {label}
      </span>
      <span
        className={cn(
          "flex items-center gap-1 truncate",
          dim ? "text-text-muted" : "text-text",
        )}
        title={value}
      >
        {icon}
        <span className="truncate">{value}</span>
      </span>
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

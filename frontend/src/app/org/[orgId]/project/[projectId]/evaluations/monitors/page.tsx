"use client";

import { useMemo, useState } from "react";
import {
  useQuery,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useProject } from "@/components/providers/ProjectProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useUrlState } from "@/hooks/useUrlState";
import { listMonitors } from "@/lib/api/evaluations";
import { getSubscription } from "@/lib/api/subscriptions";
import type { MonitorResponse } from "@/lib/api/types";
import { MonitorTable } from "@/components/features/MonitorTable";
import { MonitorDetailSidebar } from "@/components/features/MonitorDetailSidebar";
import { MonitorFormSidebar } from "@/components/features/MonitorFormSidebar";
import { Pagination } from "@/components/common/Pagination";
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
import { Radio, Sparkles, X } from "lucide-react";
import { queryKeys } from "@/lib/query/keys";
import { MonitorStatus, SubscriptionPlan } from "@/lib/api/enums";
import { extractErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";

const LIST_POLL_INTERVAL_MS = 5000;
const IMMINENT_WINDOW_MS = 2 * 60 * 1000;
const STATUS_ALL = "all";

const URL_CONFIG = {
  page: { default: "1" },
  limit: { default: "50" },
  status: { default: STATUS_ALL },
} as const;

export default function MonitorsPage() {
  const routeParams = useParams<{ orgId: string; projectId: string }>();
  const orgId = routeParams.orgId;
  const { currentProject } = useProject();
  const queryClient = useQueryClient();
  const projectId = currentProject?.id ?? routeParams.projectId ?? "";

  const { values, set, page, limit, offset, setPage, totalPages } =
    useUrlState(URL_CONFIG);

  useDocumentTitle("Monitors");

  const [selectedMonitorId, setSelectedMonitorId] = useState<string | null>(
    null,
  );
  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<MonitorResponse | null>(null);

  const listParams = useMemo(() => {
    const p: Parameters<typeof listMonitors>[0] = { limit, offset };
    if (values.status !== STATUS_ALL) {
      p.status = values.status as MonitorStatus;
    }
    return p;
  }, [limit, offset, values.status]);

  const { data, isPending, isPlaceholderData, error, refetch } = useQuery({
    queryKey: queryKeys.evaluations.monitors.list(
      projectId,
      listParams as unknown as Record<string, unknown>,
    ),
    queryFn: () => listMonitors(listParams),
    enabled: !!currentProject,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      // Poll while any listed active monitor is about to fire, so we catch
      // status flips (ACTIVE → run queued) quickly. Otherwise stay quiet.
      const items = query.state.data?.items ?? [];
      const now = Date.now();
      const imminent = items.some((m) => {
        if (m.status !== MonitorStatus.ACTIVE) return false;
        if (!m.next_run_at) return false;
        const diff = new Date(m.next_run_at).getTime() - now;
        return diff > 0 && diff < IMMINENT_WINDOW_MS;
      });
      return imminent ? LIST_POLL_INTERVAL_MS : false;
    },
    refetchIntervalInBackground: false,
  });

  // Monitors are gated to paid plans. If the org is on HOBBY we render an
  // upgrade CTA so users discover the path to unlock the feature without
  // hitting the backend error first.
  const subscriptionQuery = useQuery({
    queryKey: queryKeys.subscriptions.current(orgId),
    queryFn: () => getSubscription(orgId),
    enabled: !!orgId,
    staleTime: 60_000,
  });
  const isHobby = subscriptionQuery.data?.plan === SubscriptionPlan.HOBBY;
  const plansHref = `/org/${orgId}/settings/plans`;

  const hasActiveFilters = values.status !== STATUS_ALL;

  function clearAllFilters() {
    set({ status: STATUS_ALL, page: "1" });
  }

  function invalidateMonitorsList() {
    queryClient.invalidateQueries({
      queryKey: queryKeys.evaluations.monitors.all(projectId),
    });
  }

  function handleOpenEdit(monitor: MonitorResponse) {
    setEditTarget(monitor);
    setFormOpen(true);
    setSelectedMonitorId(null);
  }

  function handleOpenCreate() {
    setEditTarget(null);
    setFormOpen(true);
  }

  function handleFormClose() {
    setFormOpen(false);
    setEditTarget(null);
  }

  if (!currentProject) {
    return (
      <EmptyState
        title="Select a project"
        description="Choose a project to view monitors."
      />
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-96px)] animate-fade-in">
      <div className="flex-shrink-0 space-y-3 pb-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-mono text-primary">Monitors</h1>
          <div className="flex items-center gap-2">
            {isHobby && (
              <Button
                asChild
                size="sm"
                className="bg-warning/10 text-warning border border-warning/30 hover:bg-warning/20"
              >
                <Link href={plansHref}>
                  <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                  Upgrade to unlock monitors
                </Link>
              </Button>
            )}
            <Button variant="primary" size="sm" onClick={handleOpenCreate}>
              <Radio className="h-3.5 w-3.5 mr-1.5" />
              Create Monitor
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto">
          <Select
            value={values.status}
            onValueChange={(v) => set({ status: v, page: "1" })}
          >
            <SelectTrigger className="w-36 h-9 text-xs flex-shrink-0">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={STATUS_ALL}>All statuses</SelectItem>
              {Object.values(MonitorStatus).map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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
            title="No monitors"
            description={
              hasActiveFilters
                ? "Try adjusting your filters."
                : "Create a monitor to automate evaluations."
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
              <MonitorTable
                monitors={data.items}
                onSelect={(m) => setSelectedMonitorId(m.id)}
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

      <MonitorDetailSidebar
        monitorId={selectedMonitorId}
        projectId={projectId}
        orgId={orgId}
        open={selectedMonitorId !== null}
        onClose={() => setSelectedMonitorId(null)}
        onEdit={handleOpenEdit}
        onChanged={invalidateMonitorsList}
      />

      <MonitorFormSidebar
        monitor={editTarget}
        projectId={projectId}
        open={formOpen}
        onClose={handleFormClose}
        onSubmitted={invalidateMonitorsList}
      />
    </div>
  );
}

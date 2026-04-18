"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { getTraceRun, getSessionRun } from "@/lib/api/evaluations";
import { EvaluationStatus } from "@/lib/api/enums";
import type { EvalRunResponse } from "@/lib/api/types";
import { queryKeys } from "@/lib/query/keys";
import { useProjectId } from "@/hooks/useNavigation";
import {
  CORNER_STACK_SLOT_ID,
  useToast,
} from "@/components/providers/ToastProvider";
import { Tooltip } from "@/components/ui/Tooltip";
import { cn } from "@/lib/utils/cn";

/**
 * Global registry of in-flight evaluation runs for the current project,
 * used to drive automatic background polling and cache invalidation so that
 * trace/session scores appear without a manual page refresh.
 *
 * Lives inside the project layout — registry resets when the user leaves the
 * project. Pending runs that predate a tab reload are not recovered; in that
 * case the user can either manually refresh the scores sidebar or wait for
 * the runs-list polling on an evaluation page to pick them up.
 */

type EvalMode = "trace" | "session";

type PendingRun = {
  runId: string;
  mode: EvalMode;
  targetIds: string[];
  registeredAt: number;
};

type RegisterInput = Omit<PendingRun, "registeredAt">;

type EvalRunTrackerContextValue = {
  pending: PendingRun[];
  register: (run: RegisterInput) => void;
  unregister: (runId: string) => void;
};

const EvalRunTrackerContext = createContext<EvalRunTrackerContextValue | null>(
  null,
);

const TERMINAL_STATES: ReadonlySet<string> = new Set([
  EvaluationStatus.COMPLETED,
  EvaluationStatus.FAILED,
]);

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_DURATION_MS = 15 * 60 * 1000;
const CLEANUP_CHECK_INTERVAL_MS = 60_000;

export function EvalRunTrackerProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingRun[]>([]);

  const register = useCallback((run: RegisterInput) => {
    setPending((prev) => {
      if (prev.some((p) => p.runId === run.runId)) return prev;
      return [...prev, { ...run, registeredAt: Date.now() }];
    });
  }, []);

  const unregister = useCallback((runId: string) => {
    setPending((prev) => prev.filter((p) => p.runId !== runId));
  }, []);

  const value = useMemo<EvalRunTrackerContextValue>(
    () => ({ pending, register, unregister }),
    [pending, register, unregister],
  );

  return (
    <EvalRunTrackerContext.Provider value={value}>
      {children}
      <EvalRunPoller />
    </EvalRunTrackerContext.Provider>
  );
}

export function useEvalRunTracker(): EvalRunTrackerContextValue | null {
  return useContext(EvalRunTrackerContext);
}

export function useHasPendingEvalForTarget(
  mode: EvalMode,
  targetId: string | null | undefined,
): boolean {
  const tracker = useContext(EvalRunTrackerContext);
  const pending = tracker?.pending;
  return useMemo(() => {
    if (!targetId || !pending) return false;
    return pending.some(
      (p) => p.mode === mode && p.targetIds.includes(targetId),
    );
  }, [pending, mode, targetId]);
}

function EvalRunPoller() {
  const tracker = useContext(EvalRunTrackerContext);
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const projectId = useProjectId() ?? "";
  const lastStatusRef = useRef<Record<string, string>>({});

  const trackerPending = tracker?.pending;
  const pending = useMemo(() => trackerPending ?? [], [trackerPending]);
  const unregister = tracker?.unregister;

  useEffect(() => {
    if (!unregister || pending.length === 0) return;
    const timer = setInterval(() => {
      const now = Date.now();
      pending.forEach((p) => {
        if (now - p.registeredAt > MAX_POLL_DURATION_MS) {
          unregister(p.runId);
        }
      });
    }, CLEANUP_CHECK_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [pending, unregister]);

  const results = useQueries({
    queries: pending.map((p) => ({
      queryKey: ["evalRunPoll", p.mode, p.runId] as const,
      queryFn: () =>
        p.mode === "trace" ? getTraceRun(p.runId) : getSessionRun(p.runId),
      refetchInterval: (query: {
        state: { data?: { status?: string }; error: unknown };
      }) => {
        if (query.state.error) return false;
        const status = query.state.data?.status;
        if (status && TERMINAL_STATES.has(status)) return false;
        return POLL_INTERVAL_MS;
      },
      refetchIntervalInBackground: false,
      staleTime: 0,
      gcTime: 0,
    })),
  });

  useEffect(() => {
    if (!unregister) return;
    results.forEach((r, idx) => {
      const p = pending[idx];
      if (!p) return;

      if (r.error) {
        delete lastStatusRef.current[p.runId];
        unregister(p.runId);
        return;
      }

      const status = r.data?.status;
      if (!status) return;

      const prev = lastStatusRef.current[p.runId];
      lastStatusRef.current[p.runId] = status;

      if (prev === status) return;
      if (!TERMINAL_STATES.has(status)) return;

      p.targetIds.forEach((targetId) => {
        const scoresKey =
          p.mode === "trace"
            ? [...queryKeys.traces.detail(targetId), "scores"]
            : [...queryKeys.sessions.detail(targetId), "scores"];
        queryClient.invalidateQueries({ queryKey: scoresKey });
      });

      if (projectId) {
        const runsKey =
          p.mode === "trace"
            ? queryKeys.evaluations.traceRuns.all(projectId)
            : queryKeys.evaluations.sessionRuns.all(projectId);
        queryClient.invalidateQueries({ queryKey: runsKey });
      }

      showCompletionToast(toast, r.data as EvalRunResponse);

      delete lastStatusRef.current[p.runId];
      unregister(p.runId);
    });
  }, [results, pending, queryClient, unregister, projectId, toast]);

  if (pending.length === 0) return null;

  return <PendingRunsPill pending={pending} results={results} />;
}

function showCompletionToast(
  toast: ReturnType<typeof useToast>["toast"],
  run: EvalRunResponse,
) {
  const runLabel = run.name ? `'${run.name}'` : null;

  if (run.status === EvaluationStatus.FAILED) {
    const desc = [runLabel, run.error_message ?? "Something went wrong"]
      .filter(Boolean)
      .join(" · ");
    toast({
      title: "Evaluation failed",
      description: desc || undefined,
      variant: "error",
    });
    return;
  }

  if (run.status === EvaluationStatus.COMPLETED) {
    const parts: string[] = [];
    if (runLabel) parts.push(runLabel);
    const scoreWord = run.evaluated_count === 1 ? "score" : "scores";
    parts.push(`${run.evaluated_count} ${scoreWord} added`);
    if (run.failed_count > 0) parts.push(`${run.failed_count} failed`);
    toast({
      title: "Evaluation complete",
      description: parts.join(" · "),
      variant: "success",
    });
  }
}

type PollResult = {
  data?: EvalRunResponse;
  error: unknown;
  isPending?: boolean;
};

function PendingRunsPill({
  pending,
  results,
}: {
  pending: PendingRun[];
  results: PollResult[];
}) {

  const [portalTarget] = useState<HTMLElement | null>(() => {
    if (typeof document === "undefined") return null;
    return document.getElementById(CORNER_STACK_SLOT_ID);
  });

  const items = pending.map((p, idx) => ({
    pending: p,
    data: results[idx]?.data,
  }));

  const single = items.length === 1 ? items[0] : null;

  const summary = single
    ? formatSingleSummary(single)
    : `Running ${items.length} evaluations`;

  if (!portalTarget) return null;

  return createPortal(
    <Tooltip content={<PendingTooltipContent items={items} />} side="top">
      <div
        className={cn(
          "inline-flex items-center gap-2",
          "border border-info/40 bg-surface/95 px-3 py-2",
          "shadow-lg shadow-black/20 backdrop-blur-sm",
          "text-xs font-mono text-text",
        )}
      >
        <Loader2 className="h-3.5 w-3.5 animate-spin text-info" />
        <span className="truncate max-w-[280px]">{summary}</span>
      </div>
    </Tooltip>,
    portalTarget,
  );
}

function formatSingleSummary(item: {
  pending: PendingRun;
  data?: EvalRunResponse;
}): string {
  const name = item.data?.name ?? null;
  const prefix = name ? `Running '${truncate(name, 28)}'` : "Running evaluation";
  const progress = formatProgress(item.data);
  return progress ? `${prefix} · ${progress}` : prefix;
}

function formatProgress(run: EvalRunResponse | undefined): string | null {
  if (!run) return null;
  const total = run.total_targets ?? 0;
  if (total <= 0) return null;
  const done = (run.evaluated_count ?? 0) + (run.failed_count ?? 0);
  return `${done}/${total}`;
}

function PendingTooltipContent({
  items,
}: {
  items: { pending: PendingRun; data?: EvalRunResponse }[];
}) {
  return (
    <div className="space-y-1.5 min-w-[220px] max-w-[320px] max-h-[240px] overflow-y-auto py-0.5">
      {items.map((item) => {
        const name = item.data?.name ?? null;
        const progress = formatProgress(item.data);
        const status = item.data?.status ?? "Queued";
        return (
          <div key={item.pending.runId} className="text-[11px] font-mono">
            <div className="text-text truncate">
              {name ?? `${item.pending.mode} evaluation`}
            </div>
            <div className="text-text-muted">
              <span className="capitalize">{status.toLowerCase()}</span>
              {progress && <span> · {progress}</span>}
              {item.data && item.data.failed_count > 0 && (
                <span className="text-error">
                  {" "}
                  · {item.data.failed_count} failed
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return `${s.slice(0, max - 1)}…`;
}

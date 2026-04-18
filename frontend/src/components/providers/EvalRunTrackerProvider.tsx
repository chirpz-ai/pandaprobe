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
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { getTraceRun, getSessionRun } from "@/lib/api/evaluations";
import { EvaluationStatus } from "@/lib/api/enums";
import { queryKeys } from "@/lib/query/keys";
import { useProjectId } from "@/hooks/useNavigation";

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

/**
 * Returns the tracker context, or null if not mounted inside the provider.
 * Callers should no-op gracefully when null so the feature degrades rather
 * than crashing in surfaces that live outside the project layout.
 */
export function useEvalRunTracker(): EvalRunTrackerContextValue | null {
  return useContext(EvalRunTrackerContext);
}

function EvalRunPoller() {
  const tracker = useContext(EvalRunTrackerContext);
  const queryClient = useQueryClient();
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

      delete lastStatusRef.current[p.runId];
      unregister(p.runId);
    });
  }, [results, pending, queryClient, unregister, projectId]);

  return null;
}

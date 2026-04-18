"use client";

import { useEffect, useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  X,
  ChevronDown,
  ChevronRight,
  Loader2,
  FlaskConical,
} from "lucide-react";
import {
  getProviders,
  getTraceMetrics,
  getSessionMetrics,
  createBatchTraceRun,
  createBatchSessionRun,
} from "@/lib/api/evaluations";
import type {
  CreateBatchEvalRunRequest,
  CreateBatchSessionEvalRunRequest,
  EvalRunResponse,
  ProviderInfo,
  MetricSummary,
} from "@/lib/api/types";
import {
  PROVIDER_MODELS,
  DEFAULT_SIGNAL_WEIGHTS,
} from "@/lib/constants/evalModels";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import { Tooltip } from "@/components/ui/Tooltip";
import { useToast } from "@/components/providers/ToastProvider";
import { useEvalRunTracker } from "@/components/providers/EvalRunTrackerProvider";
import { extractErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";

const DEFAULT_PROVIDER_VALUE = "__default__";

type SignalWeightKey = keyof typeof DEFAULT_SIGNAL_WEIGHTS;
const SIGNAL_WEIGHT_KEYS = Object.keys(
  DEFAULT_SIGNAL_WEIGHTS,
) as SignalWeightKey[];

interface RunEvalSidebarProps {
  mode: "trace" | "session";
  open: boolean;
  onClose: () => void;
  targetIds: string[];
  onSubmitted?: () => void;
  onClearSelection?: () => void;
}

export function RunEvalSidebar({
  mode,
  open,
  onClose,
  targetIds,
  onSubmitted,
  onClearSelection,
}: RunEvalSidebarProps) {
  const { toast } = useToast();
  const tracker = useEvalRunTracker();

  const [name, setName] = useState("");
  const [selectedMetrics, setSelectedMetrics] = useState<Set<string>>(
    new Set(),
  );
  const [provider, setProvider] = useState<string>(DEFAULT_PROVIDER_VALUE);
  const [customizeWeights, setCustomizeWeights] = useState(false);
  const [weights, setWeights] = useState<Record<string, number>>({
    ...DEFAULT_SIGNAL_WEIGHTS,
  });
  const [submitting, setSubmitting] = useState(false);
  const [idsExpanded, setIdsExpanded] = useState(false);

  useEffect(() => {
    if (open) {
      setName("");
      setSelectedMetrics(new Set());
      setProvider(DEFAULT_PROVIDER_VALUE);
      setCustomizeWeights(false);
      setWeights({ ...DEFAULT_SIGNAL_WEIGHTS });
      setSubmitting(false);
      setIdsExpanded(targetIds.length <= 5);
    }
  }, [open, mode, targetIds.length]);

  const providersQuery = useQuery({
    queryKey: ["evaluations", "providers"],
    queryFn: getProviders,
    enabled: open,
  });

  const metricsQuery = useQuery({
    queryKey: [
      "evaluations",
      mode === "trace" ? "trace-metrics" : "session-metrics",
    ],
    queryFn: mode === "trace" ? getTraceMetrics : getSessionMetrics,
    enabled: open,
  });

  const providers: ProviderInfo[] = useMemo(
    () =>
      (providersQuery.data ?? []).filter((p) => p.key in PROVIDER_MODELS),
    [providersQuery.data],
  );

  const metrics: MetricSummary[] = metricsQuery.data ?? [];

  const toggleMetric = (metricName: string) => {
    setSelectedMetrics((prev) => {
      const next = new Set(prev);
      if (next.has(metricName)) next.delete(metricName);
      else next.add(metricName);
      return next;
    });
  };

  const canSubmit =
    !submitting &&
    name.trim().length > 0 &&
    selectedMetrics.size > 0 &&
    targetIds.length > 0;

  async function handleSubmit() {
    if (!canSubmit) return;

    const metricList = Array.from(selectedMetrics);
    const modelId =
      provider !== DEFAULT_PROVIDER_VALUE
        ? PROVIDER_MODELS[provider]
        : undefined;

    setSubmitting(true);
    try {
      let response: EvalRunResponse;
      if (mode === "trace") {
        const body: CreateBatchEvalRunRequest = {
          trace_ids: targetIds,
          metrics: metricList,
          name: name.trim(),
          ...(modelId ? { model: modelId } : {}),
        };
        response = await createBatchTraceRun(body);
      } else {
        const body: CreateBatchSessionEvalRunRequest = {
          session_ids: targetIds,
          metrics: metricList,
          name: name.trim(),
          ...(modelId ? { model: modelId } : {}),
          ...(customizeWeights ? { signal_weights: weights } : {}),
        };
        response = await createBatchSessionRun(body);
      }
      tracker?.register({
        runId: response.id,
        mode,
        targetIds: [...targetIds],
      });
      toast({ title: "Evaluation run queued", variant: "success" });
      onSubmitted?.();
      onClearSelection?.();
      onClose();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-bg/50" onClick={onClose} />
      )}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-[500px] max-w-[90vw] bg-surface border-l border-border",
          "flex flex-col transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between h-12 px-4 border-b border-border flex-shrink-0">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider">
            {mode} evaluation · {targetIds.length}
          </h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="px-4 py-3 border-b border-border">
            <button
              type="button"
              onClick={() => setIdsExpanded((v) => !v)}
              className="flex items-center gap-1 text-xs font-mono text-text-primary uppercase tracking-wide hover:text-accent transition-colors"
            >
              {idsExpanded ? (
                <ChevronDown className="h-2.5 w-2.5" />
              ) : (
                <ChevronRight className="h-2.5 w-2.5" />
              )}
              Target {mode}s · {targetIds.length}
            </button>
            {idsExpanded && (
              <div className="mt-2 max-h-32 overflow-y-auto border border-border/40 bg-bg p-2">
                {targetIds.length === 0 ? (
                  <p className="text-[11px] font-mono text-text-muted">
                    No targets selected
                  </p>
                ) : (
                  <ul className="space-y-0.5">
                    {targetIds.map((id) => (
                      <li
                        key={id}
                        className="text-[11px] font-mono text-text-dim truncate"
                      >
                        {id}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          <div className="px-4 py-3 border-b border-border">
            <label className="block text-xs font-mono text-text-primary uppercase tracking-wide mb-1.5">
              Name <span className="text-error">*</span>
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Eval run name"
              className="h-8 text-xs"
              disabled={submitting}
            />
          </div>

          <div className="px-4 py-3 border-b border-border">
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-mono text-text-primary uppercase tracking-wide">
                Metrics <span className="text-error">*</span>
              </label>
              <span className="text-[10px] font-mono text-text-muted">
                {selectedMetrics.size}/{metrics.length}
              </span>
            </div>
            {metricsQuery.isPending ? (
              <p className="text-[11px] font-mono text-text-muted py-2">
                Loading metrics…
              </p>
            ) : metricsQuery.error ? (
              <p className="text-[11px] font-mono text-error py-2">
                {extractErrorMessage(metricsQuery.error)}
              </p>
            ) : metrics.length === 0 ? (
              <p className="text-[11px] font-mono text-text-muted py-2">
                No metrics available
              </p>
            ) : (
              <div className="max-h-64 overflow-y-auto border border-border/40 divide-y divide-border/40">
                {metrics.map((metric) => {
                  const checked = selectedMetrics.has(metric.name);
                  return (
                    <label
                      key={metric.name}
                      className={cn(
                        "flex items-start gap-2 px-2 py-1.5 cursor-pointer hover:bg-surface-hi transition-colors",
                        checked && "bg-surface-hi/40",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleMetric(metric.name)}
                        disabled={submitting}
                        className="mt-0.5 flex-shrink-0"
                      />
                      <div className="flex-1 min-w-0">
                        <span className="text-xs font-mono text-text truncate block">
                          {metric.name}
                        </span>
                        {metric.description && (
                          <p className="mt-0.5 text-[11px] font-mono text-text-muted line-clamp-2">
                            {metric.description}
                          </p>
                        )}
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          <div className="px-4 py-3 border-b border-border">
            <label className="block text-xs font-mono text-text-primary uppercase tracking-wide mb-1.5">
              Model
            </label>
            <Select
              value={provider}
              onValueChange={setProvider}
              disabled={submitting || providersQuery.isPending}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Default" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={DEFAULT_PROVIDER_VALUE}>
                  Default
                </SelectItem>
                {providers.map((p) => {
                  const item = (
                    <SelectItem
                      key={p.key}
                      value={p.key}
                      disabled={!p.available}
                    >
                      <span className="flex items-center gap-1.5">
                        <span>{p.name}</span>
                        <span className="text-text-muted text-[11px]">
                          {PROVIDER_MODELS[p.key]}
                        </span>
                      </span>
                    </SelectItem>
                  );
                  if (!p.available && p.message) {
                    return (
                      <Tooltip key={p.key} content={p.message} side="left">
                        <div>{item}</div>
                      </Tooltip>
                    );
                  }
                  return item;
                })}
              </SelectContent>
            </Select>
            {providersQuery.error && (
              <p className="mt-1 text-[10px] font-mono text-error">
                {extractErrorMessage(providersQuery.error)}
              </p>
            )}
          </div>

          {mode === "session" && (
            <div className="px-4 py-3 border-b border-border">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={customizeWeights}
                  onChange={(e) => setCustomizeWeights(e.target.checked)}
                  disabled={submitting}
                />
                <span className="text-xs font-mono text-text-primary uppercase tracking-wide">
                  Customize signal weights
                </span>
              </label>
              {customizeWeights && (
                <div className="mt-2 space-y-2">
                  {SIGNAL_WEIGHT_KEYS.map((key) => (
                    <div key={key}>
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-[11px] font-mono text-text-dim">
                          {key}
                        </span>
                        <span className="text-[11px] font-mono text-text">
                          {weights[key].toFixed(2)}
                        </span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.05}
                        value={weights[key]}
                        onChange={(e) =>
                          setWeights((prev) => ({
                            ...prev,
                            [key]: Number(e.target.value),
                          }))
                        }
                        disabled={submitting}
                        className="w-full accent-primary"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3 flex-shrink-0">
          <Button
            variant="secondary"
            size="sm"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {submitting ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <FlaskConical className="h-3 w-3" />
            )}
            {submitting ? "Submitting…" : "Submit"}
          </Button>
        </div>
      </div>
    </>
  );
}

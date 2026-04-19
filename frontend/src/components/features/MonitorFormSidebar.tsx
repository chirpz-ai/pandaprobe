"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { X, Loader2, Radio } from "lucide-react";
import {
  getProviders,
  getTraceMetrics,
  getSessionMetrics,
  createMonitor,
  updateMonitor,
} from "@/lib/api/evaluations";
import type {
  CreateMonitorRequest,
  UpdateMonitorRequest,
  EvalRunFilters,
  SessionEvalRunFilters,
  MonitorResponse,
  ProviderInfo,
  MetricSummary,
} from "@/lib/api/types";
import { TraceStatus, MonitorCadence } from "@/lib/api/enums";
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
  SelectGroup,
  SelectLabel,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import { DateTimePicker } from "@/components/common/DateTimePicker";
import { useToast } from "@/components/providers/ToastProvider";
import { extractErrorMessage } from "@/lib/api/client";
import { queryKeys } from "@/lib/query/keys";
import { cn } from "@/lib/utils/cn";

const DEFAULT_MODEL_VALUE = "__default__";
const ANY_STATUS_VALUE = "__any__";
const ANY_HAS_ERROR_VALUE = "__any__";

type TargetType = "TRACE" | "SESSION";
type CadenceKind = "every_6h" | "daily" | "weekly" | "custom";

type SignalWeightKey = keyof typeof DEFAULT_SIGNAL_WEIGHTS;
const SIGNAL_WEIGHT_KEYS = Object.keys(
  DEFAULT_SIGNAL_WEIGHTS,
) as SignalWeightKey[];

interface MonitorFormSidebarProps {
  /** Existing monitor to edit. Omit or pass null to run in create mode. */
  monitor?: MonitorResponse | null;
  projectId: string;
  open: boolean;
  onClose: () => void;
  /** Called with the created/updated monitor after a successful submit. */
  onSubmitted?: (monitor: MonitorResponse) => void;
}

interface TraceFilterState {
  date_from: string;
  date_to: string;
  status: string;
  session_id: string;
  user_id: string;
  tags: string;
  name: string;
}

interface SessionFilterState {
  date_from: string;
  date_to: string;
  user_id: string;
  has_error: string;
  tags: string;
  min_trace_count: string;
}

const EMPTY_TRACE_FILTERS: TraceFilterState = {
  date_from: "",
  date_to: "",
  status: ANY_STATUS_VALUE,
  session_id: "",
  user_id: "",
  tags: "",
  name: "",
};

const EMPTY_SESSION_FILTERS: SessionFilterState = {
  date_from: "",
  date_to: "",
  user_id: "",
  has_error: ANY_HAS_ERROR_VALUE,
  tags: "",
  min_trace_count: "",
};

/**
 * Unified sidebar for creating or editing an evaluation monitor.
 * Pass `monitor` to enter edit mode (target_type becomes read-only,
 * submit uses PATCH via `updateMonitor`); otherwise it runs in
 * create mode and hits POST /evaluations/monitors.
 */
export function MonitorFormSidebar({
  monitor,
  projectId,
  open,
  onClose,
  onSubmitted,
}: MonitorFormSidebarProps) {
  const isEdit = !!monitor;
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [targetType, setTargetType] = useState<TargetType>("TRACE");
  const [name, setName] = useState("");
  const [selectedMetrics, setSelectedMetrics] = useState<Set<string>>(
    new Set(),
  );
  const [selectedModel, setSelectedModel] = useState<string>(DEFAULT_MODEL_VALUE);
  const [samplingRate, setSamplingRate] = useState<number>(1);
  const [traceFilters, setTraceFilters] =
    useState<TraceFilterState>(EMPTY_TRACE_FILTERS);
  const [sessionFilters, setSessionFilters] = useState<SessionFilterState>(
    EMPTY_SESSION_FILTERS,
  );
  const [cadenceKind, setCadenceKind] = useState<CadenceKind>("daily");
  const [cronExpr, setCronExpr] = useState("");
  const [onlyIfChanged, setOnlyIfChanged] = useState(true);
  const [customizeWeights, setCustomizeWeights] = useState(false);
  const [weights, setWeights] = useState<Record<string, number>>({
    ...DEFAULT_SIGNAL_WEIGHTS,
  });
  const [submitting, setSubmitting] = useState(false);

  // Re-initialize the form when the sidebar opens or the target monitor changes.
  useEffect(() => {
    if (!open) return;
    if (monitor) {
      setTargetType((monitor.target_type as TargetType) ?? "TRACE");
      setName(monitor.name ?? "");
      setSelectedMetrics(new Set(monitor.metric_names ?? []));
      setSamplingRate(monitor.sampling_rate ?? 1);
      const knownModels = Object.values(PROVIDER_MODELS).flat();
      const monitorModel = monitor.model;
      setSelectedModel(
        monitorModel != null && knownModels.includes(monitorModel)
          ? monitorModel
          : DEFAULT_MODEL_VALUE,
      );
      if (monitor.cadence?.startsWith("cron:")) {
        setCadenceKind("custom");
        setCronExpr(monitor.cadence.slice("cron:".length).trim());
      } else if (
        monitor.cadence === "every_6h" ||
        monitor.cadence === "daily" ||
        monitor.cadence === "weekly"
      ) {
        setCadenceKind(monitor.cadence);
        setCronExpr("");
      } else {
        setCadenceKind("daily");
        setCronExpr("");
      }
      setOnlyIfChanged(monitor.only_if_changed);
      // Hydrate filters from monitor.filters (opaque object). We treat it as
      // either trace- or session-shaped based on target_type.
      if (monitor.target_type === "SESSION") {
        setSessionFilters(hydrateSessionFilters(monitor.filters));
        setTraceFilters(EMPTY_TRACE_FILTERS);
      } else {
        setTraceFilters(hydrateTraceFilters(monitor.filters));
        setSessionFilters(EMPTY_SESSION_FILTERS);
      }
      setCustomizeWeights(false);
      setWeights({ ...DEFAULT_SIGNAL_WEIGHTS });
    } else {
      setTargetType("TRACE");
      setName("");
      setSelectedMetrics(new Set());
      setSelectedModel(DEFAULT_MODEL_VALUE);
      setSamplingRate(1);
      setTraceFilters(EMPTY_TRACE_FILTERS);
      setSessionFilters(EMPTY_SESSION_FILTERS);
      setCadenceKind("daily");
      setCronExpr("");
      setOnlyIfChanged(true);
      setCustomizeWeights(false);
      setWeights({ ...DEFAULT_SIGNAL_WEIGHTS });
    }
    setSubmitting(false);
  }, [open, monitor]);

  // Reset metric selection when switching target type in create mode, since
  // the metric universes differ.
  useEffect(() => {
    if (!open || isEdit) return;
    setSelectedMetrics(new Set());
  }, [targetType, isEdit, open]);

  const providersQuery = useQuery({
    queryKey: ["evaluations", "providers"],
    queryFn: getProviders,
    enabled: open,
  });

  const metricsQuery = useQuery({
    queryKey: [
      "evaluations",
      targetType === "TRACE" ? "trace-metrics" : "session-metrics",
    ],
    queryFn: targetType === "TRACE" ? getTraceMetrics : getSessionMetrics,
    enabled: open,
  });

  const providers: ProviderInfo[] = useMemo(
    () => (providersQuery.data ?? []).filter((p) => p.key in PROVIDER_MODELS),
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

  const activeFilterCount = useMemo(() => {
    if (targetType === "TRACE") return countActiveTraceFilters(traceFilters);
    return countActiveSessionFilters(sessionFilters);
  }, [targetType, traceFilters, sessionFilters]);

  const cronValid = useMemo(() => {
    if (cadenceKind !== "custom") return true;
    const tokens = cronExpr.trim().split(/\s+/).filter(Boolean);
    return tokens.length === 5;
  }, [cadenceKind, cronExpr]);

  const trimmedName = name.trim();
  const canSubmit =
    !submitting &&
    trimmedName.length > 0 &&
    selectedMetrics.size > 0 &&
    samplingRate > 0 &&
    samplingRate <= 1 &&
    cronValid;

  async function handleSubmit() {
    if (!canSubmit) return;

    const metricList = Array.from(selectedMetrics);
    const modelId =
      selectedModel !== DEFAULT_MODEL_VALUE ? selectedModel : undefined;
    const cadence =
      cadenceKind === "custom" ? `cron:${cronExpr.trim()}` : cadenceKind;
    const filters =
      targetType === "TRACE"
        ? buildTraceFilters(traceFilters)
        : buildSessionFilters(sessionFilters);

    const filtersBody = filters as Record<string, unknown> | null;

    setSubmitting(true);
    try {
      let response: MonitorResponse;
      if (isEdit && monitor) {
        const body: UpdateMonitorRequest = {
          name: trimmedName,
          metrics: metricList,
          filters: filtersBody ?? {},
          sampling_rate: samplingRate,
          model: modelId ?? null,
          cadence,
          only_if_changed: onlyIfChanged,
          ...(targetType === "SESSION" && customizeWeights
            ? { signal_weights: weights }
            : {}),
        };
        response = await updateMonitor(monitor.id, body);
      } else {
        const body: CreateMonitorRequest = {
          name: trimmedName,
          target_type: targetType,
          metrics: metricList,
          sampling_rate: samplingRate,
          cadence,
          only_if_changed: onlyIfChanged,
          ...(modelId ? { model: modelId } : {}),
          ...(filtersBody ? { filters: filtersBody } : {}),
          ...(targetType === "SESSION" && customizeWeights
            ? { signal_weights: weights }
            : {}),
        };
        response = await createMonitor(body);
      }
      toast({
        title: isEdit ? "Monitor updated" : "Monitor created",
        variant: "success",
      });
      // Invalidate list + detail so viewers pick up the change immediately.
      queryClient.invalidateQueries({
        queryKey: queryKeys.evaluations.monitors.all(projectId),
      });
      if (isEdit && monitor) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.evaluations.monitors.detail(monitor.id),
        });
      }
      onSubmitted?.(response);
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
          "fixed top-0 right-0 z-50 h-full w-[520px] max-w-[92vw] bg-surface border-l border-border",
          "flex flex-col transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between h-12 px-4 border-b border-border flex-shrink-0">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider truncate">
            {isEdit ? `Edit monitor` : "Create monitor"}
          </h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="px-4 py-3 border-b border-border">
            <label className="block text-xs font-mono text-text-primary uppercase tracking-wide mb-1.5">
              Name <RequiredDot />
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Daily prod eval"
              className="h-8 text-xs"
              disabled={submitting}
            />
          </div>

          <div className="px-4 py-3 border-b border-border">
            <label className="block text-xs font-mono text-text-primary uppercase tracking-wide mb-1.5">
              Target type <RequiredDot />
            </label>
            {isEdit ? (
              <div className="text-xs font-mono text-text">
                {targetType}{" "}
                <span className="text-text-muted">
                  (target cannot be changed after creation)
                </span>
              </div>
            ) : (
              <div className="flex gap-2">
                {(["TRACE", "SESSION"] as const).map((t) => (
                  <label
                    key={t}
                    className={cn(
                      "flex items-center gap-2 border border-border px-3 py-1.5 cursor-pointer hover:bg-surface-hi transition-colors text-xs font-mono",
                      targetType === t && "bg-surface-hi border-primary",
                    )}
                  >
                    <input
                      type="radio"
                      name="target-type"
                      value={t}
                      checked={targetType === t}
                      onChange={() => setTargetType(t)}
                      disabled={submitting}
                      className="accent-primary"
                    />
                    {t}
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="px-4 py-3 border-b border-border">
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-mono text-text-primary uppercase tracking-wide">
                Metrics <RequiredDot />
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
            <div className="flex items-center justify-between mb-2">
              <label className="block text-xs font-mono text-text-primary uppercase tracking-wide">
                Filters
              </label>
              <span className="text-[10px] font-mono text-text-muted">
                {activeFilterCount === 0
                  ? "all matching"
                  : `${activeFilterCount} active`}
              </span>
            </div>
            {targetType === "TRACE" ? (
              <TraceFilterFields
                value={traceFilters}
                onChange={setTraceFilters}
                disabled={submitting}
              />
            ) : (
              <SessionFilterFields
                value={sessionFilters}
                onChange={setSessionFilters}
                disabled={submitting}
              />
            )}
          </div>

          <div className="px-4 py-3 border-b border-border">
            <label className="block text-xs font-mono text-text-primary uppercase tracking-wide mb-1.5">
              Cadence <RequiredDot />
            </label>
            <Select
              value={cadenceKind}
              onValueChange={(v) => setCadenceKind(v as CadenceKind)}
              disabled={submitting}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={MonitorCadence.every_6h}>
                  Every 6 hours
                </SelectItem>
                <SelectItem value={MonitorCadence.daily}>Daily</SelectItem>
                <SelectItem value={MonitorCadence.weekly}>Weekly</SelectItem>
                <SelectItem value={MonitorCadence.custom}>
                  Custom (cron)
                </SelectItem>
              </SelectContent>
            </Select>
            {cadenceKind === "custom" && (
              <div className="mt-2 space-y-1">
                <Input
                  value={cronExpr}
                  onChange={(e) => setCronExpr(e.target.value)}
                  placeholder="e.g. 0 3 * * *"
                  className="h-8 text-xs font-mono"
                  disabled={submitting}
                />
                <p
                  className={cn(
                    "text-[10px] font-mono",
                    cronValid ? "text-text-muted" : "text-error",
                  )}
                >
                  {cronValid
                    ? "5 space-separated fields: minute hour day-of-month month day-of-week"
                    : "Cron must have exactly 5 space-separated fields."}
                </p>
              </div>
            )}
          </div>

          <div className="px-4 py-3 border-b border-border">
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-mono text-text-primary uppercase tracking-wide">
                Sampling rate
              </label>
              <span className="text-[11px] font-mono text-text">
                {formatSamplingRate(samplingRate)}
              </span>
            </div>
            <input
              type="range"
              min={0.05}
              max={1}
              step={0.05}
              value={samplingRate}
              onChange={(e) => setSamplingRate(Number(e.target.value))}
              disabled={submitting}
              className="w-full accent-primary"
            />
            <p className="mt-1 text-[10px] font-mono text-text-muted">
              Fraction of matching{" "}
              {targetType === "TRACE" ? "traces" : "sessions"} to evaluate on
              each run.
            </p>
          </div>

          <div className="px-4 py-3 border-b border-border">
            <label className="block text-xs font-mono text-text-primary uppercase tracking-wide mb-1.5">
              Model
            </label>
            <Select
              value={selectedModel}
              onValueChange={setSelectedModel}
              disabled={submitting || providersQuery.isPending}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Default" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={DEFAULT_MODEL_VALUE}>Default</SelectItem>
                {providers.map((p) => (
                  <SelectGroup key={p.key}>
                    <SelectLabel>{p.name}</SelectLabel>
                    {PROVIDER_MODELS[p.key].map((modelId) => (
                      <SelectItem
                        key={modelId}
                        value={modelId}
                        disabled={!p.available}
                      >
                        {modelId}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="px-4 py-3 border-b border-border">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={onlyIfChanged}
                onChange={(e) => setOnlyIfChanged(e.target.checked)}
                disabled={submitting}
              />
              <span className="text-xs font-mono text-text-primary">
                Skip run if no new data since last run
              </span>
            </label>
            <p className="mt-1 text-[10px] font-mono text-text-muted pl-6">
              When enabled, the scheduled run is skipped if no new{" "}
              {targetType === "TRACE" ? "traces" : "sessions"} matching the
              filters have appeared since the previous run.
            </p>
          </div>

          {targetType === "SESSION" && (
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
              <Radio className="h-3 w-3" />
            )}
            {submitting
              ? isEdit
                ? "Saving…"
                : "Creating…"
              : isEdit
                ? "Save"
                : "Create monitor"}
          </Button>
        </div>
      </div>
    </>
  );
}

function RequiredDot() {
  return <span className="text-error">*</span>;
}

function TraceFilterFields({
  value,
  onChange,
  disabled,
}: {
  value: TraceFilterState;
  onChange: (v: TraceFilterState) => void;
  disabled: boolean;
}) {
  const set = <K extends keyof TraceFilterState>(
    key: K,
    v: TraceFilterState[K],
  ) => onChange({ ...value, [key]: v });

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <FieldLabel label="Started after">
          <DateTimePicker
            value={value.date_from}
            onChange={(v) => set("date_from", v)}
            placeholder="After..."
          />
        </FieldLabel>
        <FieldLabel label="Started before">
          <DateTimePicker
            value={value.date_to}
            onChange={(v) => set("date_to", v)}
            placeholder="Before..."
          />
        </FieldLabel>
      </div>
      <FieldLabel label="Trace status">
        <Select
          value={value.status}
          onValueChange={(v) => set("status", v)}
          disabled={disabled}
        >
          <SelectTrigger className="h-8 text-xs">
            <SelectValue placeholder="Any" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY_STATUS_VALUE}>Any</SelectItem>
            {Object.values(TraceStatus).map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </FieldLabel>
      <FieldLabel label="Trace name contains">
        <Input
          value={value.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="substring match"
          className="h-8 text-xs"
          disabled={disabled}
        />
      </FieldLabel>
      <div className="grid grid-cols-2 gap-2">
        <FieldLabel label="Session ID">
          <Input
            value={value.session_id}
            onChange={(e) => set("session_id", e.target.value)}
            placeholder="exact match"
            className="h-8 text-xs"
            disabled={disabled}
          />
        </FieldLabel>
        <FieldLabel label="User ID">
          <Input
            value={value.user_id}
            onChange={(e) => set("user_id", e.target.value)}
            placeholder="exact match"
            className="h-8 text-xs"
            disabled={disabled}
          />
        </FieldLabel>
      </div>
      <FieldLabel label="Tags (comma-separated)">
        <Input
          value={value.tags}
          onChange={(e) => set("tags", e.target.value)}
          placeholder="e.g. production, v2"
          className="h-8 text-xs"
          disabled={disabled}
        />
      </FieldLabel>
    </div>
  );
}

function SessionFilterFields({
  value,
  onChange,
  disabled,
}: {
  value: SessionFilterState;
  onChange: (v: SessionFilterState) => void;
  disabled: boolean;
}) {
  const set = <K extends keyof SessionFilterState>(
    key: K,
    v: SessionFilterState[K],
  ) => onChange({ ...value, [key]: v });

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <FieldLabel label="Started after">
          <DateTimePicker
            value={value.date_from}
            onChange={(v) => set("date_from", v)}
            placeholder="After..."
          />
        </FieldLabel>
        <FieldLabel label="Started before">
          <DateTimePicker
            value={value.date_to}
            onChange={(v) => set("date_to", v)}
            placeholder="Before..."
          />
        </FieldLabel>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <FieldLabel label="User ID">
          <Input
            value={value.user_id}
            onChange={(e) => set("user_id", e.target.value)}
            placeholder="exact match"
            className="h-8 text-xs"
            disabled={disabled}
          />
        </FieldLabel>
        <FieldLabel label="Has error">
          <Select
            value={value.has_error}
            onValueChange={(v) => set("has_error", v)}
            disabled={disabled}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue placeholder="Any" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY_HAS_ERROR_VALUE}>Any</SelectItem>
              <SelectItem value="true">With errors</SelectItem>
              <SelectItem value="false">Without errors</SelectItem>
            </SelectContent>
          </Select>
        </FieldLabel>
      </div>
      <FieldLabel label="Tags (comma-separated)">
        <Input
          value={value.tags}
          onChange={(e) => set("tags", e.target.value)}
          placeholder="e.g. production, v2"
          className="h-8 text-xs"
          disabled={disabled}
        />
      </FieldLabel>
      <FieldLabel label="Min traces per session">
        <Input
          type="number"
          min={1}
          value={value.min_trace_count}
          onChange={(e) => set("min_trace_count", e.target.value)}
          placeholder="e.g. 3"
          className="h-8 text-xs"
          disabled={disabled}
        />
      </FieldLabel>
    </div>
  );
}

function FieldLabel({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-[10px] font-mono text-text-muted mb-0.5">
        {label}
      </label>
      {children}
    </div>
  );
}

function formatSamplingRate(rate: number): string {
  if (rate >= 1) return "100%";
  return `${Math.round(rate * 100)}%`;
}

function buildTraceFilters(state: TraceFilterState): EvalRunFilters | null {
  const filters: EvalRunFilters = {};
  let any = false;
  if (state.date_from) {
    filters.date_from = new Date(state.date_from).toISOString();
    any = true;
  }
  if (state.date_to) {
    filters.date_to = new Date(state.date_to).toISOString();
    any = true;
  }
  if (state.status && state.status !== ANY_STATUS_VALUE) {
    filters.status = state.status as EvalRunFilters["status"];
    any = true;
  }
  if (state.session_id.trim()) {
    filters.session_id = state.session_id.trim();
    any = true;
  }
  if (state.user_id.trim()) {
    filters.user_id = state.user_id.trim();
    any = true;
  }
  if (state.name.trim()) {
    filters.name = state.name.trim();
    any = true;
  }
  const tags = state.tags
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  if (tags.length > 0) {
    filters.tags = tags;
    any = true;
  }
  return any ? filters : null;
}

function buildSessionFilters(
  state: SessionFilterState,
): SessionEvalRunFilters | null {
  const filters: SessionEvalRunFilters = {};
  let any = false;
  if (state.date_from) {
    filters.date_from = new Date(state.date_from).toISOString();
    any = true;
  }
  if (state.date_to) {
    filters.date_to = new Date(state.date_to).toISOString();
    any = true;
  }
  if (state.user_id.trim()) {
    filters.user_id = state.user_id.trim();
    any = true;
  }
  if (state.has_error && state.has_error !== ANY_HAS_ERROR_VALUE) {
    filters.has_error = state.has_error === "true";
    any = true;
  }
  const tags = state.tags
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  if (tags.length > 0) {
    filters.tags = tags;
    any = true;
  }
  const trimmedMin = state.min_trace_count.trim();
  if (trimmedMin) {
    const n = parseInt(trimmedMin, 10);
    if (!Number.isNaN(n) && n >= 1) {
      filters.min_trace_count = n;
      any = true;
    }
  }
  return any ? filters : null;
}

function hydrateTraceFilters(
  raw: Record<string, unknown> | null | undefined,
): TraceFilterState {
  if (!raw) return { ...EMPTY_TRACE_FILTERS };
  const s: TraceFilterState = { ...EMPTY_TRACE_FILTERS };
  if (typeof raw.date_from === "string") s.date_from = raw.date_from;
  if (typeof raw.date_to === "string") s.date_to = raw.date_to;
  if (typeof raw.status === "string") s.status = raw.status;
  if (typeof raw.session_id === "string") s.session_id = raw.session_id;
  if (typeof raw.user_id === "string") s.user_id = raw.user_id;
  if (typeof raw.name === "string") s.name = raw.name;
  if (Array.isArray(raw.tags)) {
    s.tags = (raw.tags as unknown[])
      .filter((x) => typeof x === "string")
      .join(", ");
  }
  return s;
}

function hydrateSessionFilters(
  raw: Record<string, unknown> | null | undefined,
): SessionFilterState {
  if (!raw) return { ...EMPTY_SESSION_FILTERS };
  const s: SessionFilterState = { ...EMPTY_SESSION_FILTERS };
  if (typeof raw.date_from === "string") s.date_from = raw.date_from;
  if (typeof raw.date_to === "string") s.date_to = raw.date_to;
  if (typeof raw.user_id === "string") s.user_id = raw.user_id;
  if (typeof raw.has_error === "boolean") {
    s.has_error = raw.has_error ? "true" : "false";
  }
  if (Array.isArray(raw.tags)) {
    s.tags = (raw.tags as unknown[])
      .filter((x) => typeof x === "string")
      .join(", ");
  }
  if (typeof raw.min_trace_count === "number") {
    s.min_trace_count = String(raw.min_trace_count);
  }
  return s;
}

function countActiveTraceFilters(state: TraceFilterState): number {
  let n = 0;
  if (state.date_from) n++;
  if (state.date_to) n++;
  if (state.status && state.status !== ANY_STATUS_VALUE) n++;
  if (state.session_id.trim()) n++;
  if (state.user_id.trim()) n++;
  if (state.name.trim()) n++;
  if (
    state.tags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean).length > 0
  )
    n++;
  return n;
}

function countActiveSessionFilters(state: SessionFilterState): number {
  let n = 0;
  if (state.date_from) n++;
  if (state.date_to) n++;
  if (state.user_id.trim()) n++;
  if (state.has_error && state.has_error !== ANY_HAS_ERROR_VALUE) n++;
  if (
    state.tags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean).length > 0
  )
    n++;
  if (state.min_trace_count.trim()) n++;
  return n;
}

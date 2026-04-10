"use client";

import { useEffect, useState, useCallback } from "react";
import { useProject } from "@/components/providers/ProjectProvider";
import { getTraceAnalytics, type TraceAnalyticsParams } from "@/lib/api/traces";
import { getTraceScoreSummary } from "@/lib/api/evaluations";
import type { AnalyticsBucket, TokenCostBucket, TopModel, ScoreSummaryItem } from "@/lib/api/types";
import { AnalyticsMetric, AnalyticsGranularity } from "@/lib/api/enums";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { formatNumber, formatCost } from "@/lib/utils/format";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import { DateRangePicker } from "@/components/common/DateRangePicker";

function BarChart({ data, labelKey, valueKey, maxValue }: {
  data: Record<string, unknown>[];
  labelKey: string;
  valueKey: string;
  maxValue: number;
}) {
  return (
    <div className="space-y-1">
      {data.map((item, i) => {
        const value = Number(item[valueKey]) || 0;
        const width = maxValue > 0 ? (value / maxValue) * 100 : 0;
        return (
          <div key={i} className="flex items-center gap-2 text-xs font-mono">
            <span className="w-24 truncate text-text-dim">{String(item[labelKey])}</span>
            <div className="flex-1 h-4 bg-bg border border-border">
              <div
                className="h-full bg-accent/20 border-r border-accent/40"
                style={{ width: `${Math.max(width, 1)}%` }}
              />
            </div>
            <span className="w-16 text-right text-text-dim">{formatNumber(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function AnalyticsPage() {
  const { currentProject } = useProject();

  const defaultEnd = new Date().toISOString().slice(0, 16);
  const defaultStart = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 16);

  const [metric, setMetric] = useState<string>(AnalyticsMetric.volume);
  const [granularity, setGranularity] = useState<string>(AnalyticsGranularity.day);
  const [startDate, setStartDate] = useState(defaultStart);
  const [endDate, setEndDate] = useState(defaultEnd);

  const [analyticsData, setAnalyticsData] = useState<unknown[] | null>(null);
  const [scoreSummary, setScoreSummary] = useState<ScoreSummaryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const params: TraceAnalyticsParams = {
        metric: metric as TraceAnalyticsParams["metric"],
        granularity: granularity as TraceAnalyticsParams["granularity"],
        started_after: new Date(startDate).toISOString(),
        started_before: new Date(endDate).toISOString(),
      };
      const [analytics, scores] = await Promise.all([
        getTraceAnalytics(params),
        getTraceScoreSummary({
          date_from: new Date(startDate).toISOString(),
          date_to: new Date(endDate).toISOString(),
        }).catch(() => []),
      ]);
      setAnalyticsData(analytics);
      setScoreSummary(scores);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, [currentProject, metric, granularity, startDate, endDate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (!currentProject) {
    return <EmptyState title="Select a project" description="Choose a project to view analytics." />;
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Analytics</h1>

      <div className="flex flex-wrap items-center gap-3">
        <Select value={metric} onValueChange={setMetric}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Metric" />
          </SelectTrigger>
          <SelectContent>
            {Object.values(AnalyticsMetric).map((m) => (
              <SelectItem key={m} value={m}>{m}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={granularity} onValueChange={setGranularity}>
          <SelectTrigger className="w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.values(AnalyticsGranularity).map((g) => (
              <SelectItem key={g} value={g}>{g}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <DateRangePicker
          startDate={startDate}
          endDate={endDate}
          onStartChange={setStartDate}
          onEndChange={setEndDate}
        />
      </div>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchData} />
      ) : !analyticsData || analyticsData.length === 0 ? (
        <EmptyState title="No analytics data" description="Data will appear once traces are recorded." />
      ) : (
        <div className="space-y-6">
          {metric === "models" ? (
            <div className="border-engraved bg-surface p-4">
              <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">Top Models</h2>
              <div className="border border-border overflow-x-auto">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="border-b border-border bg-surface-hi">
                      <th className="text-left px-3 py-2 text-text-muted font-normal">Model</th>
                      <th className="text-left px-3 py-2 text-text-muted font-normal">Calls</th>
                      <th className="text-left px-3 py-2 text-text-muted font-normal">Tokens</th>
                      <th className="text-left px-3 py-2 text-text-muted font-normal">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(analyticsData as TopModel[]).map((m) => (
                      <tr key={m.model} className="border-b border-border">
                        <td className="px-3 py-2 text-text">{m.model}</td>
                        <td className="px-3 py-2 text-text-dim">{formatNumber(m.call_count)}</td>
                        <td className="px-3 py-2 text-text-dim">{formatNumber(m.total_tokens)}</td>
                        <td className="px-3 py-2 text-text-dim">{formatCost(m.total_cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : metric === "tokens" || metric === "cost" ? (
            <div className="border-engraved bg-surface p-4">
              <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
                {metric === "tokens" ? "Token Usage" : "Cost"} Over Time
              </h2>
              <BarChart
                data={analyticsData as Record<string, unknown>[]}
                labelKey="bucket"
                valueKey={metric === "tokens" ? "total_tokens" : "total_cost"}
                maxValue={Math.max(
                  ...(analyticsData as TokenCostBucket[]).map((b) =>
                    metric === "tokens" ? b.total_tokens : b.total_cost
                  )
                )}
              />
            </div>
          ) : (
            <div className="border-engraved bg-surface p-4">
              <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
                Trace {metric} Over Time
              </h2>
              <BarChart
                data={analyticsData as Record<string, unknown>[]}
                labelKey="bucket"
                valueKey={metric === "latency" ? "avg_latency_ms" : "trace_count"}
                maxValue={Math.max(
                  ...(analyticsData as AnalyticsBucket[]).map((b) =>
                    metric === "latency" ? (b.avg_latency_ms ?? 0) : b.trace_count
                  )
                )}
              />
            </div>
          )}

          {scoreSummary.length > 0 && (
            <div className="border-engraved bg-surface p-4">
              <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
                Score Summary
              </h2>
              <div className="border border-border overflow-x-auto">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="border-b border-border bg-surface-hi">
                      <th className="text-left px-3 py-2 text-text-muted font-normal">Metric</th>
                      <th className="text-left px-3 py-2 text-text-muted font-normal">Avg</th>
                      <th className="text-left px-3 py-2 text-text-muted font-normal">Min</th>
                      <th className="text-left px-3 py-2 text-text-muted font-normal">Max</th>
                      <th className="text-left px-3 py-2 text-text-muted font-normal">Success</th>
                      <th className="text-left px-3 py-2 text-text-muted font-normal">Failed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scoreSummary.map((s) => (
                      <tr key={s.metric_name} className="border-b border-border">
                        <td className="px-3 py-2 text-text">{s.metric_name}</td>
                        <td className="px-3 py-2 text-text-dim">{s.avg_score?.toFixed(2) ?? "—"}</td>
                        <td className="px-3 py-2 text-text-dim">{s.min_score?.toFixed(2) ?? "—"}</td>
                        <td className="px-3 py-2 text-text-dim">{s.max_score?.toFixed(2) ?? "—"}</td>
                        <td className="px-3 py-2 text-success">{s.success_count}</td>
                        <td className="px-3 py-2 text-error">{s.failed_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

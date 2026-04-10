"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ListTree, Layers, CheckCircle, BarChart3 } from "lucide-react";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useResolvedProjectId } from "@/hooks/useNavigation";
import { listTraces } from "@/lib/api/traces";
import { listSessions } from "@/lib/api/sessions";
import { listMonitors } from "@/lib/api/evaluations";
import { getUsage } from "@/lib/api/subscriptions";
import { formatNumber, formatCost } from "@/lib/utils/format";
import { LoadingState } from "@/components/common/LoadingState";
import type { UsageResponse } from "@/lib/api/types";

interface DashboardStats {
  traceCount: number;
  sessionCount: number;
  monitorCount: number;
  usage: UsageResponse | null;
}

export default function DashboardPage() {
  const { orgId } = useParams();
  const { projects } = useOrganization();
  const projectId = useResolvedProjectId(projects);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      setLoading(true);
      try {
        const [traces, sessions, monitors, usage] = await Promise.allSettled([
          projectId ? listTraces({ limit: 1 }) : Promise.resolve(null),
          projectId ? listSessions({ limit: 1 }) : Promise.resolve(null),
          projectId ? listMonitors({ limit: 1 }) : Promise.resolve(null),
          getUsage(),
        ]);

        setStats({
          traceCount:
            traces.status === "fulfilled" && traces.value
              ? traces.value.total
              : 0,
          sessionCount:
            sessions.status === "fulfilled" && sessions.value
              ? sessions.value.total
              : 0,
          monitorCount:
            monitors.status === "fulfilled" && monitors.value
              ? monitors.value.total
              : 0,
          usage:
            usage.status === "fulfilled" ? usage.value : null,
        });
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, [projectId]);

  if (loading) return <LoadingState />;

  const projectBase = projectId ? `/org/${orgId}/project/${projectId}` : null;

  const cards = [
    {
      label: "Traces",
      value: formatNumber(stats?.traceCount ?? 0),
      icon: <ListTree className="h-4 w-4" />,
      href: projectBase ? `${projectBase}/traces` : "#",
    },
    {
      label: "Sessions",
      value: formatNumber(stats?.sessionCount ?? 0),
      icon: <Layers className="h-4 w-4" />,
      href: projectBase ? `${projectBase}/sessions` : "#",
    },
    {
      label: "Monitors",
      value: formatNumber(stats?.monitorCount ?? 0),
      icon: <CheckCircle className="h-4 w-4" />,
      href: projectBase ? `${projectBase}/evaluations/monitors` : "#",
    },
    {
      label: "Period Cost",
      value: stats?.usage
        ? formatCost(
            (stats.usage.traces + stats.usage.trace_evals + stats.usage.session_evals) * 0
          )
        : "—",
      icon: <BarChart3 className="h-4 w-4" />,
      href: projectBase ? `${projectBase}/analytics` : "#",
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Home</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((card) => (
          <Link
            key={card.label}
            href={card.href}
            className="border-engraved bg-surface p-4 hover:bg-surface-hi transition-colors"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono text-text-dim uppercase tracking-wider">
                {card.label}
              </span>
              <span className="text-text-muted">{card.icon}</span>
            </div>
            <span className="text-2xl font-mono text-primary">{card.value}</span>
          </Link>
        ))}
      </div>

      {stats?.usage && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-dim uppercase tracking-wider mb-4">
            Current Period Usage
          </h2>
          <div className="grid grid-cols-3 gap-6">
            <div>
              <span className="text-xs text-text-muted block">Traces</span>
              <span className="text-sm font-mono text-text">
                {formatNumber(stats.usage.traces)}
              </span>
            </div>
            <div>
              <span className="text-xs text-text-muted block">Trace Evals</span>
              <span className="text-sm font-mono text-text">
                {formatNumber(stats.usage.trace_evals)}
              </span>
            </div>
            <div>
              <span className="text-xs text-text-muted block">Session Evals</span>
              <span className="text-sm font-mono text-text">
                {formatNumber(stats.usage.session_evals)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

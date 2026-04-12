"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ListTree, Layers, CheckCircle, BarChart3 } from "lucide-react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { listTraces } from "@/lib/api/traces";
import { listSessions } from "@/lib/api/sessions";
import { listMonitors } from "@/lib/api/evaluations";
import { getUsage } from "@/lib/api/subscriptions";
import { queryKeys } from "@/lib/query/keys";
import { formatNumber } from "@/lib/utils/format";
import { LoadingState } from "@/components/common/LoadingState";

export default function ProjectHomePage() {
  const { orgId, projectId } = useParams();

  useDocumentTitle("Home");

  const tracesQuery = useQuery({
    queryKey: [...queryKeys.dashboardStats.home(projectId as string), "traces"],
    queryFn: () => listTraces({ limit: 1 }),
  });

  const sessionsQuery = useQuery({
    queryKey: [...queryKeys.dashboardStats.home(projectId as string), "sessions"],
    queryFn: () => listSessions({ limit: 1 }),
  });

  const monitorsQuery = useQuery({
    queryKey: [...queryKeys.dashboardStats.home(projectId as string), "monitors"],
    queryFn: () => listMonitors({ limit: 1 }),
  });

  const usageQuery = useQuery({
    queryKey: queryKeys.subscriptions.usage,
    queryFn: getUsage,
  });

  const hasData = tracesQuery.data || sessionsQuery.data || monitorsQuery.data;
  const initialLoading =
    tracesQuery.isPending || sessionsQuery.isPending || monitorsQuery.isPending;

  if (initialLoading && !hasData) return <LoadingState />;

  const projectBase = `/org/${orgId}/project/${projectId}`;

  const cards = [
    {
      label: "Traces",
      value: formatNumber(tracesQuery.data?.total ?? 0),
      icon: <ListTree className="h-4 w-4" />,
      href: `${projectBase}/traces`,
    },
    {
      label: "Sessions",
      value: formatNumber(sessionsQuery.data?.total ?? 0),
      icon: <Layers className="h-4 w-4" />,
      href: `${projectBase}/sessions`,
    },
    {
      label: "Monitors",
      value: formatNumber(monitorsQuery.data?.total ?? 0),
      icon: <CheckCircle className="h-4 w-4" />,
      href: `${projectBase}/evaluations/monitors`,
    },
    {
      label: "Period Usage",
      value: usageQuery.data
        ? formatNumber(
            usageQuery.data.traces +
              usageQuery.data.trace_evals +
              usageQuery.data.session_evals
          )
        : "—",
      icon: <BarChart3 className="h-4 w-4" />,
      href: `${projectBase}/analytics`,
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
            <span className="text-2xl font-mono text-primary">
              {card.value}
            </span>
          </Link>
        ))}
      </div>

      {usageQuery.data && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-dim uppercase tracking-wider mb-4">
            Current Period Usage
          </h2>
          <div className="grid grid-cols-3 gap-6">
            <div>
              <span className="text-xs text-text-muted block">Traces</span>
              <span className="text-sm font-mono text-text">
                {formatNumber(usageQuery.data.traces)}
              </span>
            </div>
            <div>
              <span className="text-xs text-text-muted block">Trace Evals</span>
              <span className="text-sm font-mono text-text">
                {formatNumber(usageQuery.data.trace_evals)}
              </span>
            </div>
            <div>
              <span className="text-xs text-text-muted block">
                Session Evals
              </span>
              <span className="text-sm font-mono text-text">
                {formatNumber(usageQuery.data.session_evals)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

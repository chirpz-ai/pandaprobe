"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  CheckCircle,
  Layers,
  ListTree,
  Rocket,
} from "lucide-react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { listTraces } from "@/lib/api/traces";
import { listSessions } from "@/lib/api/sessions";
import { listMonitors } from "@/lib/api/evaluations";
import { getUsage } from "@/lib/api/subscriptions";
import { queryKeys } from "@/lib/query/keys";
import { formatNumber } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/common/LoadingState";
import { InstructionSidebar } from "@/components/features/InstructionSidebar";
import { SkillOnboarding } from "@/components/features/SkillOnboarding";

export default function ProjectHomePage() {
  const { orgId, projectId } = useParams();
  const [resourcesOpen, setResourcesOpen] = useState(false);

  useDocumentTitle("Home");

  const tracesQuery = useQuery({
    queryKey: [...queryKeys.dashboardStats.home(projectId as string), "traces"],
    queryFn: () => listTraces({ limit: 1 }),
  });

  const sessionsQuery = useQuery({
    queryKey: [
      ...queryKeys.dashboardStats.home(projectId as string),
      "sessions",
    ],
    queryFn: () => listSessions({ limit: 1 }),
  });

  const monitorsQuery = useQuery({
    queryKey: [
      ...queryKeys.dashboardStats.home(projectId as string),
      "monitors",
    ],
    queryFn: () => listMonitors({ limit: 1 }),
  });

  const usageQuery = useQuery({
    queryKey: queryKeys.subscriptions.usage(orgId as string),
    queryFn: () => getUsage(orgId as string),
  });

  const hasData = tracesQuery.data || sessionsQuery.data || monitorsQuery.data;
  const initialLoading =
    tracesQuery.isPending || sessionsQuery.isPending || monitorsQuery.isPending;

  if (initialLoading && !hasData) return <LoadingState />;

  const projectBase = `/org/${orgId}/project/${projectId}`;

  const cards = [
    {
      label: "Traces",
      description: "Recorded runs",
      value: formatNumber(tracesQuery.data?.total ?? 0),
      icon: ListTree,
      color: "text-brand-blue",
      href: `${projectBase}/traces`,
    },
    {
      label: "Sessions",
      description: "Related runs",
      value: formatNumber(sessionsQuery.data?.total ?? 0),
      icon: Layers,
      color: "text-brand-green",
      href: `${projectBase}/sessions`,
    },
    {
      label: "Monitors",
      description: "Recurring evaluations",
      value: formatNumber(monitorsQuery.data?.total ?? 0),
      icon: CheckCircle,
      color: "text-brand-yellow",
      href: `${projectBase}/evaluations/monitors`,
    },
    {
      label: "Period usage",
      description: "Organization events this period",
      value: formatNumber(usageQuery.data?.total_events),
      icon: BarChart3,
      color: "text-text-dim",
      href: `${projectBase}/analytics`,
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Home</h1>

      <div className="border-engraved bg-surface p-5 space-y-4 animate-fade-in">
        <div className="flex flex-col sm:flex-row items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <span className="flex-shrink-0 text-primary">
              <Rocket className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <h2 className="text-base font-mono text-text">Get started</h2>
              <p className="text-sm font-mono text-text-muted mt-0.5 leading-relaxed">
                Paste the prompt into your coding agent and it handles the
                setup. Or install the skill yourself.
              </p>
            </div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setResourcesOpen(true)}
            className="flex-shrink-0"
          >
            <BookOpen className="h-3 w-3" />
            Quickstart guides
          </Button>
        </div>
        <SkillOnboarding />
      </div>

      <section
        aria-label="Project overview"
        className="overflow-hidden rounded-panel border border-border bg-surface"
      >
        <div className="grid grid-cols-2 lg:grid-cols-4">
          {cards.map(({ icon: Icon, ...card }, index) => (
            <Link
              key={card.label}
              href={card.href}
              className={cn(
                "group flex min-w-0 flex-col gap-5 p-4 sm:p-5 transition-colors hover:bg-surface-hi/60 focus-visible:bg-surface-hi/60 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary",
                index % 2 === 1 && "border-l border-divider",
                index >= 2 && "border-t border-divider lg:border-t-0",
                index === 2 && "lg:border-l",
              )}
            >
              <div className="flex items-center gap-2">
                <Icon
                  aria-hidden="true"
                  className={cn("h-4 w-4 shrink-0", card.color)}
                />
                <span className="font-sans text-xs sm:text-sm text-text-dim group-hover:text-text group-focus-visible:text-text">
                  {card.label}
                </span>
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 break-words font-sans text-2xl font-medium tracking-tight tabular-nums text-primary">
                    {card.value}
                  </span>
                  <ArrowRight
                    aria-hidden="true"
                    className="h-3.5 w-3.5 shrink-0 text-text-muted transition-colors group-hover:text-primary group-focus-visible:text-primary"
                  />
                </div>
                <span className="block font-sans text-caption text-text-muted">
                  {card.description}
                </span>
              </div>
            </Link>
          ))}
        </div>

        {usageQuery.data && (
          <div className="flex flex-col gap-4 border-t border-divider px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <h2 className="font-sans text-xs text-text-dim">Usage breakdown</h2>
            <dl className="grid grid-cols-3 gap-4 sm:gap-8">
              {[
                { label: "Traces", value: usageQuery.data.traces },
                { label: "Trace evals", value: usageQuery.data.trace_evals },
                {
                  label: "Session evals",
                  value: usageQuery.data.session_evals,
                },
              ].map((item) => (
                <div key={item.label} className="min-w-0 space-y-1">
                  <dt className="font-sans text-caption text-text-muted">
                    {item.label}
                  </dt>
                  <dd className="break-words font-sans text-sm tabular-nums text-text">
                    {formatNumber(item.value)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </section>

      <InstructionSidebar
        open={resourcesOpen}
        onClose={() => setResourcesOpen(false)}
      />
    </div>
  );
}

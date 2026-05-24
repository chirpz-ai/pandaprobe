"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
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
import { Accordion } from "@/components/common/Accordion";
import { LoadingState } from "@/components/common/LoadingState";
import { InstructionCard } from "@/components/features/InstructionCard";
import { InstructionSidebar } from "@/components/features/InstructionSidebar";
import type { InstructionId } from "@/components/features/InstructionContent";

interface QuickstartEntry {
  id: InstructionId;
  step: number;
  title: string;
  description: string;
}

const QUICKSTART_ENTRIES: QuickstartEntry[] = [
  {
    id: "quickstart",
    step: 1,
    title: "Send your first trace",
    description:
      "Install the SDK, mint an API key, and wrap your LLM client to trace your first call.",
  },
  {
    id: "agent-quickstart",
    step: 2,
    title: "Trace your agent",
    description:
      "Instrument advanced agent frameworks like DeepAgents, CrewAI, and more.",
  },
  {
    id: "evaluation-quickstart",
    step: 3,
    title: "Evaluate your agent",
    description:
      "Set up monitors and eval runs to score your agent's traces and sessions.",
  },
];

export default function ProjectHomePage() {
  const { orgId, projectId } = useParams();
  const [activeInstruction, setActiveInstruction] =
    useState<InstructionId | null>(null);

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
  const hasAnyTrace = (tracesQuery.data?.total ?? 0) > 0;

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
              usageQuery.data.session_evals,
          )
        : "—",
      icon: <BarChart3 className="h-4 w-4" />,
      href: `${projectBase}/analytics`,
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Home</h1>

      <Accordion
        title="Quickstarts"
        description="Short, focused walkthroughs to get you tracing, instrumenting agents, and running evals."
        icon={<Rocket className="h-4 w-4" />}
        defaultOpen={!hasAnyTrace}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 divide-y divide-border md:divide-y-0 md:divide-x">
          {QUICKSTART_ENTRIES.map((entry, index) => (
            <InstructionCard
              key={entry.id}
              instructionId={entry.id}
              step={entry.step}
              title={entry.title}
              description={entry.description}
              highlight={index === 0 && !hasAnyTrace}
              onClick={() => setActiveInstruction(entry.id)}
            />
          ))}
        </div>
      </Accordion>

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

      <InstructionSidebar
        instructionId={activeInstruction ?? "quickstart"}
        open={activeInstruction !== null}
        onClose={() => setActiveInstruction(null)}
      />
    </div>
  );
}

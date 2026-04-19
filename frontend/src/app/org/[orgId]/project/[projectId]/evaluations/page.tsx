"use client";

import Link from "next/link";
import { ListTree, Layers, Radio, Gauge } from "lucide-react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useProjectPath } from "@/hooks/useNavigation";

export default function EvaluationsPage() {
  const basePath = useProjectPath();

  useDocumentTitle("Evaluations");

  const sections = [
    {
      title: "Trace Evaluation Runs",
      description: "Run evaluation metrics against individual traces",
      href: basePath + "/evaluations/trace-runs",
      icon: <ListTree className="h-5 w-5" />,
    },
    {
      title: "Session Evaluation Runs",
      description: "Run evaluation metrics against entire sessions",
      href: basePath + "/evaluations/session-runs",
      icon: <Layers className="h-5 w-5" />,
    },
    {
      title: "Trace Scores",
      description:
        "Browse and filter every score produced for traces across runs, metrics, and environments",
      href: basePath + "/evaluations/trace-scores",
      icon: <Gauge className="h-5 w-5" />,
    },
    {
      title: "Session Scores",
      description:
        "Browse and filter every score produced for sessions across runs and metrics",
      href: basePath + "/evaluations/session-scores",
      icon: <Gauge className="h-5 w-5" />,
    },
    {
      title: "Monitors",
      description: "Automated evaluation schedules that run periodically",
      href: basePath + "/evaluations/monitors",
      icon: <Radio className="h-5 w-5" />,
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Evaluations</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sections.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="border-engraved bg-surface p-5 hover:bg-surface-hi transition-colors"
          >
            <div className="text-text-muted mb-3">{s.icon}</div>
            <h2 className="text-sm font-mono text-text mb-1">{s.title}</h2>
            <p className="text-xs text-text-dim">{s.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

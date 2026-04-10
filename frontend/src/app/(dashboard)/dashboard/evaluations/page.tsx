"use client";

import Link from "next/link";
import { ListTree, Layers, Radio } from "lucide-react";

const sections = [
  {
    title: "Trace Evaluation Runs",
    description: "Run evaluation metrics against individual traces",
    href: "/dashboard/evaluations/trace-runs",
    icon: <ListTree className="h-5 w-5" />,
  },
  {
    title: "Session Evaluation Runs",
    description: "Run evaluation metrics against entire sessions",
    href: "/dashboard/evaluations/session-runs",
    icon: <Layers className="h-5 w-5" />,
  },
  {
    title: "Monitors",
    description: "Automated evaluation schedules that run periodically",
    href: "/dashboard/evaluations/monitors",
    icon: <Radio className="h-5 w-5" />,
  },
];

export default function EvaluationsPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Evaluations</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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

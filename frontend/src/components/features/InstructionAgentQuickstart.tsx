"use client";

import { Bot, Construction } from "lucide-react";

export function InstructionAgentQuickstart() {
  return <ComingSoon icon={<Bot className="h-5 w-5" />} title="Agent Quickstart" />;
}

function ComingSoon({
  icon,
  title,
}: {
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-20 space-y-4">
      <div className="flex items-center justify-center h-12 w-12 border border-border bg-surface-hi text-text-muted">
        {icon}
      </div>
      <div className="space-y-1">
        <h3 className="text-sm font-mono text-text">{title}</h3>
        <p className="text-xs font-mono text-text-muted max-w-sm">
          Step-by-step walkthrough coming soon.
        </p>
      </div>
      <div className="flex items-center gap-1.5 px-3 py-1.5 border border-warning/40 bg-warning/10 text-warning text-[11px] font-mono">
        <Construction className="h-3 w-3" />
        Under construction
      </div>
    </div>
  );
}

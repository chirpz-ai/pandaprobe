"use client";

import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils/cn";
import { getInstruction, type InstructionId } from "./InstructionContent";

interface InstructionCardProps {
  instructionId: InstructionId;
  step: number;
  title?: string;
  description?: string;
  ctaLabel?: string;
  highlight?: boolean;
  onClick: () => void;
}

export function InstructionCard({
  instructionId,
  step,
  title,
  description,
  ctaLabel = "Open",
  highlight = false,
  onClick,
}: InstructionCardProps) {
  const instruction = getInstruction(instructionId);
  const displayTitle = title ?? instruction.title;
  const displayDescription = description ?? instruction.description;

  return (
    <div className="flex flex-col gap-2 p-4">
      <div className="flex items-center gap-3">
        <span className="flex-shrink-0 flex items-center justify-center h-7 w-7 border border-border bg-surface-hi text-xs font-mono text-text-dim">
          {String(step).padStart(2, "0")}
        </span>
        <h3 className="flex-1 min-w-0 truncate text-sm font-mono text-text">
          {displayTitle}
        </h3>
        <Button
          variant="secondary"
          size="sm"
          onClick={onClick}
          className={cn(highlight && "border-text/60 animate-pulse-glow")}
        >
          {ctaLabel}
          <ArrowRight className="h-3 w-3" />
        </Button>
      </div>

      <p className="pl-10 text-xs font-mono text-text-muted leading-snug">
        {displayDescription}
      </p>
    </div>
  );
}

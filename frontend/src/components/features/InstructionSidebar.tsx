"use client";

import { X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils/cn";
import {
  InstructionContent,
  getInstruction,
  type InstructionId,
} from "./InstructionContent";

interface InstructionSidebarProps {
  instructionId: InstructionId;
  open: boolean;
  onClose: () => void;
}

export function InstructionSidebar({
  instructionId,
  open,
  onClose,
}: InstructionSidebarProps) {
  const { icon: Icon, title, description } = getInstruction(instructionId);

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-bg/50" onClick={onClose} />
      )}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-[1000px] max-w-[95vw] bg-surface border-l border-border",
          "flex flex-col transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
        aria-hidden={!open}
      >
        <div className="flex items-center justify-between h-12 px-4 border-b border-border flex-shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <Icon className="h-4 w-4 text-primary flex-shrink-0" />
            <h2 className="text-xs font-mono text-primary uppercase tracking-wider truncate">
              {title}
            </h2>
            <span className="text-[11px] font-mono text-text-dim truncate hidden sm:inline">
              · {description}
            </span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label={`Close ${title}`}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5">
          {open && <InstructionContent instructionId={instructionId} />}
        </div>
      </div>
    </>
  );
}

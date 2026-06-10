"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils/cn";
import {
  InstructionContent,
  INSTRUCTIONS,
  type InstructionId,
} from "./InstructionContent";

interface InstructionSidebarProps {
  open: boolean;
  onClose: () => void;
  initialInstructionId?: InstructionId;
}

const TABS = Object.values(INSTRUCTIONS);

export function InstructionSidebar({
  open,
  onClose,
  initialInstructionId = "quickstart",
}: InstructionSidebarProps) {
  const [active, setActive] = useState<InstructionId>(initialInstructionId);

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
        <div className="flex items-center gap-2 h-12 px-3 border-b border-border flex-shrink-0">
          <div className="flex items-center gap-1 min-w-0 overflow-x-auto scrollbar-hide">
            {TABS.map(({ id, title, icon: Icon }) => {
              const isActive = id === active;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setActive(id)}
                  aria-pressed={isActive}
                  className={cn(
                    "inline-flex items-center gap-1.5 px-2.5 py-1.5 border text-xs font-mono whitespace-nowrap transition-colors",
                    isActive
                      ? "border-primary/40 bg-primary/10 text-primary"
                      : "border-transparent text-text-dim hover:text-text hover:bg-surface-hi",
                  )}
                >
                  <Icon className="h-3.5 w-3.5 flex-shrink-0" />
                  {title}
                </button>
              );
            })}
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close resources"
            className="ml-auto flex-shrink-0"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5">
          {open && <InstructionContent instructionId={active} />}
        </div>
      </div>
    </>
  );
}

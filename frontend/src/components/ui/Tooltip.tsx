"use client";

import { type ReactNode } from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils/cn";

interface TooltipProps {
  children: ReactNode;
  content: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  sideOffset?: number;
  delayDuration?: number;
  className?: string;
}

export function Tooltip({
  children,
  content,
  side = "top",
  sideOffset = 6,
  delayDuration = 200,
  className,
}: TooltipProps) {
  return (
    <TooltipPrimitive.Provider delayDuration={delayDuration}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            sideOffset={sideOffset}
            className={cn(
              "z-50 bg-surface border border-border px-2 py-1 text-xs font-mono text-text animate-fade-in",
              className,
            )}
          >
            {content}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}

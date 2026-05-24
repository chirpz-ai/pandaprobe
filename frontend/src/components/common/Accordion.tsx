"use client";

import { type ReactNode } from "react";
import * as AccordionPrimitive from "@radix-ui/react-accordion";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils/cn";

interface AccordionProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  trailing?: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  children: ReactNode;
}

export function Accordion({
  title,
  description,
  icon,
  trailing,
  defaultOpen = true,
  className,
  children,
}: AccordionProps) {
  const value = "accordion-item";

  return (
    <AccordionPrimitive.Root
      type="single"
      collapsible
      defaultValue={defaultOpen ? value : undefined}
      className={cn("border-engraved bg-surface animate-fade-in", className)}
    >
      <AccordionPrimitive.Item value={value}>
        <AccordionPrimitive.Header asChild>
          <h2>
            <AccordionPrimitive.Trigger
              className={cn(
                "group w-full flex items-center gap-3 px-4 py-3 text-left",
                "hover:bg-surface-hi transition-colors",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent",
              )}
            >
              {icon && (
                <span className="flex-shrink-0 text-text-muted">{icon}</span>
              )}
              <div className="flex-1 min-w-0">
                <span className="block text-sm font-mono text-text">
                  {title}
                </span>
                {description && (
                  <span className="block text-xs font-mono text-text-muted mt-0.5 leading-snug truncate">
                    {description}
                  </span>
                )}
              </div>
              {trailing && (
                <span className="flex-shrink-0 text-text-dim">{trailing}</span>
              )}
              <ChevronDown
                className={cn(
                  "h-3.5 w-3.5 flex-shrink-0 text-text-dim transition-transform",
                  "group-data-[state=open]:rotate-180",
                )}
              />
            </AccordionPrimitive.Trigger>
          </h2>
        </AccordionPrimitive.Header>
        <AccordionPrimitive.Content className="overflow-hidden border-t border-border data-[state=closed]:hidden">
          {children}
        </AccordionPrimitive.Content>
      </AccordionPrimitive.Item>
    </AccordionPrimitive.Root>
  );
}

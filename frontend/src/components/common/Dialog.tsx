"use client";

import type { ReactNode } from "react";
import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils/cn";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  titleIcon?: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  locked?: boolean;
  className?: string;
}

export function Dialog({
  open,
  onOpenChange,
  title,
  titleIcon,
  description,
  children,
  locked = false,
  className,
}: DialogProps) {
  function handleOpenChange(v: boolean) {
    if (locked && !v) return;
    onOpenChange(v);
  }

  return (
    <RadixDialog.Root open={open} onOpenChange={handleOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <RadixDialog.Content
          onPointerDownOutside={(e) => {
            if (locked) e.preventDefault();
          }}
          onEscapeKeyDown={(e) => {
            if (locked) e.preventDefault();
          }}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 border border-border bg-surface p-6 animate-fade-in",
            className,
          )}
        >
          <div className="flex items-start justify-between mb-4">
            <RadixDialog.Title className="text-sm font-mono text-primary flex items-center gap-2">
              {titleIcon}
              {title}
            </RadixDialog.Title>
            {!locked && (
              <RadixDialog.Close className="text-text-muted hover:text-text transition-colors">
                <X className="h-4 w-4" />
              </RadixDialog.Close>
            )}
          </div>
          {description ? (
            <RadixDialog.Description className="text-xs text-text-dim mb-4">
              {description}
            </RadixDialog.Description>
          ) : (
            <RadixDialog.Description className="sr-only">
              {title}
            </RadixDialog.Description>
          )}
          {children}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

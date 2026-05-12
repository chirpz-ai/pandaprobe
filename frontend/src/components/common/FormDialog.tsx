"use client";

import { useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Button, type ButtonProps } from "@/components/ui/Button";

interface FormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  titleIcon?: ReactNode;
  description?: ReactNode;
  variant?: "default" | "destructive";
  submitLabel?: string;
  submitVariant?: ButtonProps["variant"];
  submitDisabled?: boolean;
  onSubmit: () => Promise<void>;
  children: ReactNode;
}

export function FormDialog({
  open,
  onOpenChange,
  title,
  titleIcon,
  description,
  variant = "default",
  submitLabel = "Submit",
  submitVariant,
  submitDisabled = false,
  onSubmit,
  children,
}: FormDialogProps) {
  const [loading, setLoading] = useState(false);

  const destructive = variant === "destructive";
  const resolvedSubmitVariant =
    submitVariant ?? (destructive ? "destructive" : "primary");

  function handleOpenChange(v: boolean) {
    if (!loading) onOpenChange(v);
  }

  async function handleSubmit() {
    setLoading(true);
    try {
      await onSubmit();
      handleOpenChange(false);
    } catch {
      // Error handling is delegated to the onSubmit caller
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 bg-surface p-6 animate-fade-in",
            destructive ? "border border-error/30" : "border border-border",
          )}
        >
          <div className="flex items-start justify-between mb-4">
            <Dialog.Title
              className={cn(
                "text-sm font-mono flex items-center gap-2",
                destructive ? "text-error" : "text-primary",
              )}
            >
              {titleIcon}
              {title}
            </Dialog.Title>
            <Dialog.Close
              disabled={loading}
              className="text-text-muted hover:text-text transition-colors disabled:opacity-50"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>
          {description ? (
            <Dialog.Description className="text-xs text-text-dim mb-4">
              {description}
            </Dialog.Description>
          ) : (
            <Dialog.Description className="sr-only">
              {title}
            </Dialog.Description>
          )}
          <div className="space-y-4">
            {children}
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={loading}
                onClick={() => handleOpenChange(false)}
              >
                Cancel
              </Button>
              <Button
                variant={resolvedSubmitVariant}
                size="sm"
                disabled={loading || submitDisabled}
                onClick={handleSubmit}
              >
                {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {submitLabel}
              </Button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

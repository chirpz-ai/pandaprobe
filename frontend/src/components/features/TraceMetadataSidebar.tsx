"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Check, Copy, PanelRight, X } from "lucide-react";
import type { TraceResponse } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils/format";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface TraceMetadataSidebarProps {
  trace: TraceResponse;
  copiedId: boolean;
  onCopyId: () => void;
}

/** Trace metadata in a drawer with keyboard dismissal and focus restoration. */
export function TraceMetadataSidebar({
  trace,
  copiedId,
  onCopyId,
}: TraceMetadataSidebarProps) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <Button variant="secondary" size="sm" className="px-2 sm:px-3">
          <PanelRight className="h-3 w-3" />
          Metadata
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-bg/50" />
        <Dialog.Content className="fixed top-0 right-0 z-50 flex h-dvh w-[500px] max-w-[90vw] flex-col border-l border-border bg-surface focus:outline-none data-[state=open]:animate-slide-in-right data-[state=closed]:animate-slide-out-right motion-reduce:animate-none">
          <div className="flex h-12 shrink-0 items-center justify-between border-b border-divider px-4">
            <Dialog.Title className="text-xs font-mono text-text-muted">
              Metadata
            </Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Close metadata">
                <X className="h-3.5 w-3.5" />
              </Button>
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">
            Identifiers and metadata for {trace.name}.
          </Dialog.Description>
          <div className="min-h-0 flex-1 space-y-6 overflow-y-auto p-4 font-mono [overflow-wrap:anywhere]">
            <h3 className="text-sm text-primary">{trace.name}</h3>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-5 text-xs">
              <div className="col-span-2 space-y-1">
                <dt className="text-text-muted">Trace ID</dt>
                <dd>
                  <button
                    type="button"
                    onClick={onCopyId}
                    aria-label="Copy trace ID"
                    className="inline-flex max-w-full items-start gap-2 text-left text-text hover:text-primary focus-visible:outline focus-visible:outline-primary"
                  >
                    <span className="min-w-0">{trace.trace_id}</span>
                    {copiedId ? (
                      <Check className="mt-0.5 h-3 w-3 shrink-0 text-success" />
                    ) : (
                      <Copy className="mt-0.5 h-3 w-3 shrink-0" />
                    )}
                    <span className="sr-only" role="status">
                      {copiedId ? "Copied" : ""}
                    </span>
                  </button>
                </dd>
              </div>
              <div className="col-span-2 space-y-1">
                <dt className="text-text-muted">Session ID</dt>
                <dd className="text-text">{trace.session_id ?? "—"}</dd>
              </div>
              {/* TODO(cost): Restore Total Cost once trace cost computation is implemented. */}
              <div className="space-y-1">
                <dt className="text-text-muted">Started</dt>
                <dd className="text-text">
                  {formatDateTime(trace.started_at)}
                </dd>
              </div>
              <div className="space-y-1">
                <dt className="text-text-muted">Ended</dt>
                <dd className="text-text">{formatDateTime(trace.ended_at)}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-text-muted">User</dt>
                <dd className="ph-no-capture text-text">
                  {trace.user_id ?? "—"}
                </dd>
              </div>
              <div className="space-y-1">
                <dt className="text-text-muted">Environment</dt>
                <dd className="text-text">{trace.environment ?? "—"}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-text-muted">Release</dt>
                <dd className="text-text">{trace.release ?? "—"}</dd>
              </div>
              <div className="col-span-2 space-y-1.5">
                <dt className="text-text-muted">Tags</dt>
                <dd className="text-text">
                  {trace.tags.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {trace.tags.map((tag) => (
                        <Badge key={tag} variant="default">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
            </dl>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

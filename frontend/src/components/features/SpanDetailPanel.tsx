"use client";

import { useState, type ReactNode } from "react";
import { ChevronRight, ChevronDown, AlertTriangle } from "lucide-react";
import type { SpanResponse, TraceResponse } from "@/lib/api/types";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { JsonViewer } from "@/components/common/JsonViewer";
import { formatDateTime, formatDuration, formatCost } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";

interface SpanDetailPanelProps {
  trace: TraceResponse;
  span: SpanResponse | null;
  mode: "trace" | "span";
}

export function SpanDetailPanel({ trace, span, mode }: SpanDetailPanelProps) {
  if (mode === "trace") {
    return <TraceDetail trace={trace} />;
  }

  if (!span) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-text-muted font-mono">
        Select a span to view details
      </div>
    );
  }

  return <SpanDetail span={span} />;
}

function TraceDetail({ trace }: { trace: TraceResponse }) {
  return (
    <div className="space-y-0">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-xs font-mono text-primary truncate">
          {trace.name}
        </h3>
        <span className="text-[10px] font-mono text-text-muted">
          Trace overview
        </span>
      </div>

      {trace.input != null && (
        <DetailSection title="Input" defaultOpen>
          <div className="pl-1">
            <JsonViewer data={trace.input} />
          </div>
        </DetailSection>
      )}

      {trace.output != null && (
        <DetailSection title="Output" defaultOpen>
          <div className="pl-1">
            <JsonViewer data={trace.output} />
          </div>
        </DetailSection>
      )}

      {Object.keys(trace.metadata).length > 0 && (
        <DetailSection title="Metadata">
          <div className="pl-1">
            <JsonViewer data={trace.metadata} />
          </div>
        </DetailSection>
      )}
    </div>
  );
}

function SpanDetail({ span }: { span: SpanResponse }) {
  const hasTokens =
    span.token_usage && Object.keys(span.token_usage).length > 0;
  const hasCost = span.cost && Object.keys(span.cost).length > 0;
  const hasModelParams =
    span.model_parameters && Object.keys(span.model_parameters).length > 0;
  const hasMetadata = Object.keys(span.metadata).length > 0;

  return (
    <div className="space-y-0">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="text-xs font-mono text-primary truncate max-w-[200px]">
            {span.name}
          </h3>
          <Badge variant="default">{span.kind}</Badge>
          <StatusBadge status={span.status} />
          {span.model && <Badge variant="info">{span.model}</Badge>}
        </div>
      </div>

      {/* Info grid */}
      <DetailSection title="Info" defaultOpen>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2">
          <KV label="Latency" value={formatDuration(span.latency_ms)} />
          <KV
            label="Time to first token"
            value={formatDuration(span.time_to_first_token_ms)}
          />
          <KV label="Started" value={formatDateTime(span.started_at)} />
          <KV label="Ended" value={formatDateTime(span.ended_at)} />
          {span.completion_start_time && (
            <KV
              label="Completion start"
              value={formatDateTime(span.completion_start_time)}
            />
          )}
        </div>
      </DetailSection>

      {/* Error */}
      {span.error && (
        <DetailSection
          title="Error"
          defaultOpen
          titleClassName="text-error"
          icon={<AlertTriangle className="h-3 w-3 text-error" />}
        >
          <pre className="text-xs font-mono text-error/80 whitespace-pre-wrap break-words bg-error/5 p-2.5 border border-error/20">
            {span.error}
          </pre>
        </DetailSection>
      )}

      {/* Input */}
      {span.input != null && (
        <DetailSection title="Input" defaultOpen>
          <div className="pl-1">
            <JsonViewer data={span.input} />
          </div>
        </DetailSection>
      )}

      {/* Output */}
      {span.output != null && (
        <DetailSection title="Output" defaultOpen>
          <div className="pl-1">
            <JsonViewer data={span.output} />
          </div>
        </DetailSection>
      )}

      {/* Token Usage */}
      {hasTokens && (
        <DetailSection title="Token Usage">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            {Object.entries(span.token_usage!).map(([k, v]) => (
              <KV key={k} label={k} value={String(v ?? "—")} />
            ))}
          </div>
        </DetailSection>
      )}

      {/* Cost */}
      {hasCost && (
        <DetailSection title="Cost">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            {Object.entries(span.cost!).map(([k, v]) => (
              <KV key={k} label={k} value={formatCost(v)} />
            ))}
          </div>
        </DetailSection>
      )}

      {/* Model Parameters */}
      {hasModelParams && (
        <DetailSection title="Model Parameters">
          <div className="pl-1">
            <JsonViewer data={span.model_parameters} />
          </div>
        </DetailSection>
      )}

      {/* Metadata */}
      {hasMetadata && (
        <DetailSection title="Metadata">
          <div className="pl-1">
            <JsonViewer data={span.metadata} />
          </div>
        </DetailSection>
      )}
    </div>
  );
}

function DetailSection({
  title,
  children,
  defaultOpen = false,
  titleClassName,
  icon,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  titleClassName?: string;
  icon?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-2 hover:bg-surface-hi transition-colors"
      >
        {open ? (
          <ChevronDown className="h-3 w-3 text-text-muted flex-shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 text-text-muted flex-shrink-0" />
        )}
        {icon}
        <span
          className={cn(
            "text-[10px] font-mono uppercase tracking-wider text-text-muted",
            titleClassName,
          )}
        >
          {title}
        </span>
      </button>
      {open && <div className="px-4 pb-3">{children}</div>}
    </div>
  );
}

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-[10px] font-mono text-text-muted block">
        {label}
      </span>
      <span className="text-xs font-mono text-text">{value}</span>
    </div>
  );
}

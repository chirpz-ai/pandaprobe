"use client";

import { useId, useState, type ReactNode } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import {
  ChevronRight,
  ChevronDown,
  AlertTriangle,
  Copy,
  Check,
} from "lucide-react";
import type { SpanResponse, TraceResponse } from "@/lib/api/types";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { JsonViewer } from "@/components/common/JsonViewer";
import { FormattedData } from "@/components/common/FormattedData";
import {
  formatDateTime,
  formatDuration,
  formatCost,
  formatTokens,
} from "@/lib/utils/format";
import { spanDuration, timestamp } from "@/lib/utils/trace-timeline";
import { cn } from "@/lib/utils/cn";

interface SpanDetailPanelProps {
  trace: TraceResponse;
  span: SpanResponse | null;
  mode: "trace" | "span";
}

export function SpanDetailPanel({ trace, span, mode }: SpanDetailPanelProps) {
  const [view, setView] = useState("formatted");
  const selected = mode === "span" ? span : null;
  const record = selected ?? trace;
  const parent = trace.spans.find(
    (item) => item.span_id === selected?.parent_span_id,
  );
  const start = timestamp(selected?.started_at ?? null);
  const traceStart = timestamp(trace.started_at);
  const offset =
    start != null && traceStart != null ? start - traceStart : null;
  const renderData = (data: unknown) =>
    view === "raw" ? <JsonViewer data={data} /> : <FormattedData data={data} />;

  return (
    <Tabs.Root value={view} onValueChange={setView} className="min-w-0">
      <div className="sticky top-0 z-10 border-b border-divider bg-surface px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-[10px] font-mono uppercase tracking-wider text-text-muted">
            {selected
              ? `Span detail · ${trace.spans.indexOf(selected) + 1} / ${trace.spans.length}`
              : "Trace overview"}
          </span>
          <Tabs.List
            aria-label="Content format"
            className="flex border border-border p-0.5"
          >
            <Tabs.Trigger
              value="formatted"
              className="px-2.5 py-1 text-[10px] font-mono text-text-muted data-[state=active]:bg-surface-hi data-[state=active]:text-primary focus-visible:outline focus-visible:outline-primary"
            >
              Formatted
            </Tabs.Trigger>
            <Tabs.Trigger
              value="raw"
              className="px-2.5 py-1 text-[10px] font-mono text-text-muted data-[state=active]:bg-surface-hi data-[state=active]:text-primary focus-visible:outline focus-visible:outline-primary"
            >
              Raw
            </Tabs.Trigger>
          </Tabs.List>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 min-w-0">
          <h2 className="text-sm font-mono text-primary [overflow-wrap:anywhere]">
            {record.name}
          </h2>
          {selected && <Badge variant="default">{selected.kind}</Badge>}
          <StatusBadge status={record.status} />
        </div>
      </div>
      {/* Keep the selected format when navigating between spans. */}
      <Tabs.Content
        value={view}
        className="min-w-0 focus-visible:outline-none"
        key={selected?.span_id ?? "trace"}
      >
        <div className="mx-4 mt-3 mb-1 rounded-md border border-divider bg-bg/30 p-3 grid grid-cols-2 gap-x-4 gap-y-3">
          {selected ? (
            <>
              <KV
                label="Start"
                value={
                  offset != null
                    ? `${offset >= 0 ? "+" : "−"}${formatDuration(Math.abs(offset))}`
                    : "—"
                }
              />
              <KV
                label="Duration"
                value={formatDuration(spanDuration(selected))}
              />
              {selected.model && <KV label="Model" value={selected.model} />}
              {selected.parent_span_id && (
                <KV
                  label="Parent"
                  value={parent?.name ?? selected.parent_span_id}
                />
              )}
              {selected.time_to_first_token_ms != null && (
                <KV
                  label="First token"
                  value={formatDuration(selected.time_to_first_token_ms)}
                />
              )}
            </>
          ) : (
            <>
              <KV
                label="Total tokens"
                value={formatTokens(trace.total_tokens)}
              />
              <KV label="Spans" value={String(trace.spans.length)} />
            </>
          )}
        </div>
        {selected?.error && (
          <DetailSection
            title="Error"
            icon={<AlertTriangle className="h-3 w-3 text-error" />}
          >
            <pre className="ph-no-capture whitespace-pre-wrap [overflow-wrap:anywhere] border border-error/20 bg-error/5 p-3 text-xs text-error">
              {selected.error}
            </pre>
          </DetailSection>
        )}
        <DataSection title="Input" data={record.input}>
          {renderData(record.input)}
        </DataSection>
        <DataSection title="Output" data={record.output}>
          {renderData(record.output)}
        </DataSection>
        {selected?.token_usage &&
          Object.keys(selected.token_usage).length > 0 && (
            <DataSection title="Token usage" data={selected.token_usage}>
              {renderData(selected.token_usage)}
            </DataSection>
          )}
        {selected?.cost && Object.keys(selected.cost).length > 0 && (
          <DetailSection title="Cost">
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(selected.cost).map(([key, value]) => (
                <KV key={key} label={key} value={formatCost(value)} />
              ))}
            </div>
          </DetailSection>
        )}
        {selected?.model_parameters &&
          Object.keys(selected.model_parameters).length > 0 && (
            <DataSection
              title="Model parameters"
              data={selected.model_parameters}
            >
              {renderData(selected.model_parameters)}
            </DataSection>
          )}
        {Object.keys(record.metadata).length > 0 && (
          <DataSection title="Metadata" data={record.metadata}>
            {renderData(record.metadata)}
          </DataSection>
        )}
        {selected && (
          <DetailSection
            title="Span identifiers & timestamps"
            defaultOpen={false}
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <KV label="Span ID" value={selected.span_id} copyable />
              {selected.parent_span_id && (
                <KV
                  label="Parent span ID"
                  value={selected.parent_span_id}
                  copyable
                />
              )}
              <KV label="Started" value={formatDateTime(selected.started_at)} />
              <KV label="Ended" value={formatDateTime(selected.ended_at)} />
              {selected.completion_start_time && (
                <KV
                  label="Completion start"
                  value={formatDateTime(selected.completion_start_time)}
                />
              )}
            </div>
          </DetailSection>
        )}
      </Tabs.Content>
    </Tabs.Root>
  );
}

function DataSection({
  title,
  data,
  children,
}: {
  title: string;
  data: unknown;
  children: ReactNode;
}) {
  return (
    <DetailSection
      title={title}
      action={
        <CopyValue
          value={
            typeof data === "string"
              ? data
              : (JSON.stringify(data, null, 2) ?? "null")
          }
          label={`Copy ${title.toLowerCase()}`}
        />
      }
    >
      {children}
    </DetailSection>
  );
}

function DetailSection({
  title,
  children,
  defaultOpen = true,
  icon,
  action,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className="py-1">
      <div className="mx-2 flex items-center justify-between gap-2">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={() => setOpen((value) => !value)}
          className="inline-flex max-w-full items-center gap-2 rounded-md px-2 py-2.5 text-left text-text-muted hover:text-text transition-colors focus-visible:outline focus-visible:outline-primary"
        >
          {open ? (
            <ChevronDown className="h-3 w-3 shrink-0" />
          ) : (
            <ChevronRight className="h-3 w-3 shrink-0" />
          )}
          {icon}
          <span className="text-[10px] font-mono uppercase tracking-wider">
            {title}
          </span>
        </button>
        {action}
      </div>
      <div
        id={id}
        hidden={!open}
        className="px-4 pb-4 min-w-0 [overflow-wrap:anywhere]"
      >
        {open && children}
      </div>
    </div>
  );
}

function CopyValue({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }
  return (
    <button
      type="button"
      onClick={copy}
      onBlur={() => {
        setCopied(false);
        setFailed(false);
      }}
      aria-label={copied ? `${label}: copied` : label}
      title={
        failed
          ? "Copy failed. Select the text to copy it."
          : copied
            ? "Copied"
            : label
      }
      className={cn(
        "flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-text-muted hover:bg-surface-hi/60 hover:text-text transition-colors focus-visible:outline focus-visible:outline-primary",
        copied && "text-success",
      )}
    >
      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
    </button>
  );
}

function KV({
  label,
  value,
  copyable,
}: {
  label: string;
  value: string;
  copyable?: boolean;
}) {
  return (
    <div className="min-w-0">
      <span className="block text-[10px] font-mono text-text-muted">
        {label}
      </span>
      <div className="flex items-center gap-1">
        <span className="text-xs font-mono text-text [overflow-wrap:anywhere]">
          {value}
        </span>
        {copyable && (
          <CopyValue value={value} label={`Copy ${label.toLowerCase()}`} />
        )}
      </div>
    </div>
  );
}

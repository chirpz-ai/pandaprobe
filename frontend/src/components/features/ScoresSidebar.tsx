"use client";

import { useState, useCallback } from "react";
import {
  X,
  MessageSquareText,
  Clock,
  RefreshCw,
  FlaskConical,
  ChevronRight,
  ChevronDown,
  Globe,
  Settings,
  User,
} from "lucide-react";
import type { TraceScoreResponse, SessionScoreResponse } from "@/lib/api/types";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatDateTime } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";

type ScoreItem = TraceScoreResponse | SessionScoreResponse;

interface ScoresSidebarProps {
  scores: ScoreItem[];
  open: boolean;
  onClose: () => void;
}

export function ScoresSidebar({ scores, open, onClose }: ScoresSidebarProps) {
  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-bg/50" onClick={onClose} />
      )}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-[500px] max-w-[90vw] bg-surface border-l border-border",
          "flex flex-col transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between h-12 px-4 border-b border-border flex-shrink-0">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider">
            Scores · {scores.length}
          </h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          {scores.length === 0 ? (
            <div className="flex items-center justify-center h-full text-xs text-text-muted font-mono">
              No scores available
            </div>
          ) : (
            <div className="divide-y divide-border">
              {scores.map((score) => (
                <ScoreRow key={score.id} score={score} />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function ScoreRow({ score }: { score: ScoreItem }) {
  const traceScore = "trace_id" in score ? (score as TraceScoreResponse) : null;

  return (
    <div className="px-4 py-3 hover:bg-surface-hi transition-colors">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-text">
          <span className="text-primary">{score.name}</span>
          <span className="text-primary mx-1.5">=</span>
          <span className="text-primary font-medium">
            {score.value ?? "—"}
          </span>
        </span>
        <StatusBadge status={score.status} />
      </div>

      <div className="flex items-center gap-1.5 mb-2">
        <Badge variant="default">{score.data_type}</Badge>
        <Badge variant="default">{score.source}</Badge>
      </div>

      {score.reason && (
        <div className="flex items-start gap-1 mb-2">
          <MessageSquareText className="h-3 w-3 text-text-muted mt-0.5 flex-shrink-0" />
          <p className="text-xs font-mono text-text-dim whitespace-pre-wrap">
            <span className="text-text-muted">Reasoning:</span> {score.reason}
          </p>
        </div>
      )}

      {score.metadata && Object.keys(score.metadata).length > 0 && (
        <MetadataSection data={score.metadata} />
      )}

      <div className="space-y-0.5 text-[10px] font-mono text-text-muted mt-2">
        {traceScore?.environment && (
          <div className="flex items-center gap-1.5">
            <Globe className="h-2.5 w-2.5" />
            <span>Environment: {traceScore.environment}</span>
          </div>
        )}
        {traceScore?.config_id && (
          <div className="flex items-center gap-1.5">
            <Settings className="h-2.5 w-2.5" />
            <span className="truncate">Config: {traceScore.config_id}</span>
          </div>
        )}
        {score.author_user_id && (
          <div className="flex items-center gap-1.5">
            <User className="h-2.5 w-2.5" />
            <span className="truncate">Author: {score.author_user_id}</span>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <Clock className="h-2.5 w-2.5" />
          <span>Created {formatDateTime(score.created_at)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <RefreshCw className="h-2.5 w-2.5" />
          <span>Updated {formatDateTime(score.updated_at)}</span>
        </div>
        {score.eval_run_id && (
          <div className="flex items-center gap-1.5">
            <FlaskConical className="h-2.5 w-2.5" />
            <span className="truncate">Eval run: {score.eval_run_id}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function MetadataSection({ data }: { data: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(true);
  const toggle = useCallback(() => setExpanded((e) => !e), []);

  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={toggle}
        className="flex items-center gap-1 text-[10px] font-mono text-text-muted uppercase tracking-wide mb-1 hover:text-text transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-2.5 w-2.5" />
        ) : (
          <ChevronRight className="h-2.5 w-2.5" />
        )}
        Metadata
      </button>
      {expanded && (
        <div className="border border-border bg-bg p-2 overflow-x-auto">
          <MetadataValue data={data} depth={0} />
        </div>
      )}
    </div>
  );
}

function MetadataValue({
  data,
  depth,
}: {
  data: unknown;
  depth: number;
}) {
  if (data === null || data === undefined) {
    return <span className="text-text-muted text-[11px] font-mono">null</span>;
  }

  if (typeof data === "string" || typeof data === "number" || typeof data === "boolean") {
    return <PrimitiveValue value={data} />;
  }

  if (Array.isArray(data)) {
    if (data.length === 0) return <span className="text-text-muted text-[11px] font-mono">[]</span>;

    const allPrimitive = data.every(
      (v) => typeof v === "string" || typeof v === "number" || typeof v === "boolean",
    );

    if (allPrimitive) {
      return (
        <div className="flex flex-wrap gap-1">
          {data.map((item, i) => (
            <Badge key={i} variant="default" className="text-[10px]">
              {String(item)}
            </Badge>
          ))}
        </div>
      );
    }

    if (isObjectArray(data)) {
      return <ObjectArrayTable items={data as Record<string, unknown>[]} depth={depth} />;
    }

    return (
      <div className="space-y-0.5 pl-2 border-l border-border/50">
        {data.map((item, i) => (
          <div key={i}>
            <MetadataValue data={item} depth={depth + 1} />
          </div>
        ))}
      </div>
    );
  }

  if (typeof data === "object") {
    const entries = Object.entries(data as Record<string, unknown>);
    if (entries.length === 0) {
      return <span className="text-text-muted text-[11px] font-mono">{"{}"}</span>;
    }

    const allLeaf = entries.every(
      ([, v]) => v === null || typeof v !== "object",
    );

    if (allLeaf && depth > 0) {
      return <FlatKVTable entries={entries} />;
    }

    return (
      <div className={cn("space-y-1", depth > 0 && "pl-2 border-l border-border/50")}>
        {entries.map(([key, val]) => {
          const isComplex = val !== null && typeof val === "object";
          if (isComplex) {
            return <NestedSection key={key} label={key} value={val} depth={depth} />;
          }
          return (
            <div key={key} className="flex items-baseline gap-1.5 text-[11px] font-mono">
              <span className="text-text-muted flex-shrink-0">{key}:</span>
              <PrimitiveValue value={val} />
            </div>
          );
        })}
      </div>
    );
  }

  return <span className="text-text-dim text-[11px] font-mono">{String(data)}</span>;
}

function PrimitiveValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-text-muted text-[11px] font-mono">null</span>;
  }
  if (typeof value === "boolean") {
    return (
      <span className={cn("text-[11px] font-mono", value ? "text-success" : "text-error")}>
        {String(value)}
      </span>
    );
  }
  if (typeof value === "number") {
    const formatted = Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
    return <span className="text-info text-[11px] font-mono">{formatted}</span>;
  }
  return <span className="text-text-dim text-[11px] font-mono">{String(value)}</span>;
}

function FlatKVTable({ entries }: { entries: [string, unknown][] }) {
  return (
    <table className="text-[11px] font-mono w-full">
      <tbody>
        {entries.map(([key, val]) => (
          <tr key={key}>
            <td className="text-text-muted pr-3 py-px whitespace-nowrap align-top">{key}</td>
            <td className="text-text py-px"><PrimitiveValue value={val} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ObjectArrayTable({
  items,
  depth,
}: {
  items: Record<string, unknown>[];
  depth: number;
}) {
  const allKeys = Array.from(new Set(items.flatMap((item) => Object.keys(item))));

  const allLeaf = items.every((item) =>
    Object.values(item).every((v) => v === null || typeof v !== "object"),
  );

  if (!allLeaf) {
    return (
      <div className="space-y-1 pl-2 border-l border-border/50">
        {items.map((item, i) => (
          <MetadataValue key={i} data={item} depth={depth + 1} />
        ))}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="text-[11px] font-mono w-full border-collapse">
        <thead>
          <tr className="border-b border-border">
            {allKeys.map((k) => (
              <th key={k} className="text-text-muted text-left pr-3 py-0.5 font-normal whitespace-nowrap">
                {k}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i} className="border-b border-border/30 last:border-0">
              {allKeys.map((k) => (
                <td key={k} className="pr-3 py-0.5 whitespace-nowrap">
                  <PrimitiveValue value={item[k]} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NestedSection({
  label,
  value,
  depth,
}: {
  label: string;
  value: unknown;
  depth: number;
}) {
  const [open, setOpen] = useState(depth < 1);
  const toggle = useCallback(() => setOpen((e) => !e), []);

  return (
    <div>
      <button
        type="button"
        onClick={toggle}
        className="flex items-center gap-1 text-[11px] font-mono text-text-muted hover:text-text transition-colors"
      >
        {open ? <ChevronDown className="h-2.5 w-2.5" /> : <ChevronRight className="h-2.5 w-2.5" />}
        {label}
      </button>
      {open && (
        <div className="mt-0.5">
          <MetadataValue data={value} depth={depth + 1} />
        </div>
      )}
    </div>
  );
}

function isObjectArray(arr: unknown[]): boolean {
  return arr.length > 0 && arr.every((v) => v !== null && typeof v === "object" && !Array.isArray(v));
}

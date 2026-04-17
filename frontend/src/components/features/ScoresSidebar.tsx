"use client";

import { useState, useCallback, useMemo } from "react";
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
  SquarePen,
  Save,
  XCircle,
  Loader2,
  Trash2,
} from "lucide-react";
import type { TraceScoreResponse, SessionScoreResponse } from "@/lib/api/types";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { formatDateTime } from "@/lib/utils/format";
import { cn } from "@/lib/utils/cn";
import {
  updateTraceScore,
  deleteTraceScore,
  deleteSessionScore,
} from "@/lib/api/evaluations";
import { extractErrorMessage } from "@/lib/api/client";
import { useToast } from "@/components/providers/ToastProvider";

type ScoreItem = TraceScoreResponse | SessionScoreResponse;

interface ScoresSidebarProps {
  scores: ScoreItem[];
  open: boolean;
  onClose: () => void;
  onScoreUpdated?: () => void;
  onScoreDeleted?: () => void;
}

export function ScoresSidebar({
  scores,
  open,
  onClose,
  onScoreUpdated,
  onScoreDeleted,
}: ScoresSidebarProps) {
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
                <ScoreRow
                  key={score.id}
                  score={score}
                  onScoreUpdated={onScoreUpdated}
                  onScoreDeleted={onScoreDeleted}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function ScoreRow({
  score,
  onScoreUpdated,
  onScoreDeleted,
}: {
  score: ScoreItem;
  onScoreUpdated?: () => void;
  onScoreDeleted?: () => void;
}) {
  const { toast } = useToast();
  const traceScore = "trace_id" in score ? (score as TraceScoreResponse) : null;
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function handleDelete() {
    try {
      if (traceScore) {
        await deleteTraceScore(score.id);
      } else {
        await deleteSessionScore(score.id);
      }
      toast({ title: "Score deleted", variant: "success" });
      onScoreDeleted?.();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  if (editing && traceScore) {
    return (
      <EditableTraceScoreRow
        score={traceScore}
        onCancel={() => setEditing(false)}
        onSaved={() => {
          setEditing(false);
          onScoreUpdated?.();
        }}
      />
    );
  }

  return (
    <div className="px-4 py-3 hover:bg-surface-hi transition-colors">
      <div className="flex items-center justify-between mb-2 gap-2">
        <span className="text-xs font-mono text-text min-w-0 truncate">
          <span className="text-warning font-medium">{score.name}</span>
          <span className="text-warning mx-1.5">=</span>
          <span className="text-warning font-semibold">
            {score.value ?? "—"}
          </span>
        </span>
        <div className="flex items-center gap-1 flex-shrink-0">
          {traceScore && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 gap-1 text-text-muted hover:text-text"
              onClick={() => setEditing(true)}
              aria-label="Annotate score"
            >
              <SquarePen className="h-3 w-3" />
              annotate
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 gap-1 text-text-muted hover:text-error"
            onClick={() => setConfirmDelete(true)}
            aria-label="Delete score"
          >
            <Trash2 className="h-3 w-3" />
            delete
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-1.5 mb-2">
        <Badge variant="default">{score.data_type}</Badge>
        <Badge variant="info">{score.source}</Badge>
        <StatusBadge status={score.status} />
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

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete score"
        description={`Delete score "${score.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={handleDelete}
        destructive
      />
    </div>
  );
}

function EditableTraceScoreRow({
  score,
  onCancel,
  onSaved,
}: {
  score: TraceScoreResponse;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const [value, setValue] = useState(score.value ?? "");
  const [reason, setReason] = useState(score.reason ?? "");
  const [metadataText, setMetadataText] = useState(() =>
    JSON.stringify(score.metadata ?? {}, null, 2),
  );
  const [saving, setSaving] = useState(false);

  const metadataError = useMemo<string | null>(() => {
    const trimmed = metadataText.trim();
    if (!trimmed) return null;
    try {
      const parsed = JSON.parse(trimmed);
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        return "Metadata must be a JSON object";
      }
      return null;
    } catch (e) {
      return e instanceof Error ? e.message : "Invalid JSON";
    }
  }, [metadataText]);

  async function handleSave() {
    let parsedMetadata: Record<string, unknown> | null = null;
    const trimmed = metadataText.trim();
    if (trimmed) {
      try {
        parsedMetadata = JSON.parse(trimmed) as Record<string, unknown>;
      } catch {
        toast({ title: "Invalid metadata JSON", variant: "error" });
        return;
      }
    } else {
      parsedMetadata = {};
    }

    setSaving(true);
    try {
      await updateTraceScore(score.id, {
        value: value.trim() === "" ? null : value,
        reason: reason.trim() === "" ? null : reason,
        metadata: parsedMetadata,
      });
      toast({ title: "Score updated", variant: "success" });
      onSaved();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="px-4 py-3 bg-surface-hi/30">
      <div className="flex items-center justify-between mb-2 gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-xs font-mono text-warning font-medium whitespace-nowrap">
            {score.name}
          </span>
          <span className="text-text-muted text-xs font-mono">=</span>
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="value"
            className="h-7 text-xs px-2 flex-1 min-w-0"
            disabled={saving}
          />
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <Button
            variant="primary"
            size="sm"
            onClick={handleSave}
            disabled={saving || metadataError !== null}
            aria-label="Save score"
          >
            {saving ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Save className="h-3 w-3" />
            )}
            {saving ? "Saving…" : "Save"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={onCancel}
            disabled={saving}
            aria-label="Cancel edit"
          >
            <XCircle className="h-3 w-3" />
            Cancel
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-1.5 mb-2">
        <Badge variant="default">{score.data_type}</Badge>
        <Badge variant="info">{score.source}</Badge>
        <StatusBadge status={score.status} />
      </div>

      <div className="mb-2">
        <label className="block text-[10px] font-mono text-text-muted uppercase tracking-wide mb-1">
          Reason
        </label>
        <Textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reasoning for this score"
          className="min-h-[60px] text-xs"
          disabled={saving}
        />
      </div>

      <div className="mb-2">
        <label className="block text-[10px] font-mono text-text-muted uppercase tracking-wide mb-1">
          Metadata (JSON)
        </label>
        <Textarea
          value={metadataText}
          onChange={(e) => setMetadataText(e.target.value)}
          placeholder="{}"
          spellCheck={false}
          className={cn(
            "min-h-[140px] text-[11px] leading-relaxed",
            metadataError && "border-error focus-visible:border-error focus-visible:ring-error",
          )}
          disabled={saving}
        />
        {metadataError && (
          <p className="mt-1 text-[10px] font-mono text-error">
            {metadataError}
          </p>
        )}
      </div>

      <div className="space-y-0.5 text-[10px] font-mono text-text-muted mt-2">
        {score.environment && (
          <div className="flex items-center gap-1.5">
            <Globe className="h-2.5 w-2.5" />
            <span>Environment: {score.environment}</span>
          </div>
        )}
        {score.config_id && (
          <div className="flex items-center gap-1.5">
            <Settings className="h-2.5 w-2.5" />
            <span className="truncate">Config: {score.config_id}</span>
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

    const leafEntries = entries.filter(([, v]) => v === null || typeof v !== "object");
    const nestedEntries = entries.filter(([, v]) => v !== null && typeof v === "object");

    return (
      <div className={cn("space-y-1.5", depth > 0 && "pl-2 border-l border-border/50")}>
        {leafEntries.length > 0 && <FlatKVTable entries={leafEntries} />}
        {nestedEntries.map(([key, val]) => (
          <NestedSection key={key} label={key} value={val} depth={depth} />
        ))}
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
    <div className="overflow-x-auto border border-border/40">
      <table className="text-[11px] font-mono w-full border-collapse">
        <tbody>
          {entries.map(([key, val]) => (
            <tr key={key} className="border-b border-border/40 last:border-0">
              <td className="text-text-muted px-2 py-0.5 whitespace-nowrap align-top border-r border-border/40">
                {key}
              </td>
              <td className="text-text px-2 py-0.5">
                <PrimitiveValue value={val} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
    <div className="overflow-x-auto border border-border/40">
      <table className="text-[11px] font-mono w-full border-collapse">
        <thead>
          <tr className="border-b border-border/40 bg-surface-hi/30">
            {allKeys.map((k) => (
              <th key={k} className="text-text-muted text-left px-2 py-0.5 font-normal whitespace-nowrap">
                {k}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i} className="border-b border-border/20 last:border-0">
              {allKeys.map((k) => (
                <td key={k} className="px-2 py-0.5 whitespace-nowrap">
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
        className="flex items-center gap-1 text-[11px] font-mono text-text-muted hover:text-text transition-colors py-0.5"
      >
        {open ? <ChevronDown className="h-2.5 w-2.5" /> : <ChevronRight className="h-2.5 w-2.5" />}
        <span className="font-medium">{label}</span>
      </button>
      {open && (
        <div className="mt-0.5 ml-1">
          <MetadataValue data={value} depth={depth + 1} />
        </div>
      )}
    </div>
  );
}

function isObjectArray(arr: unknown[]): boolean {
  return arr.length > 0 && arr.every((v) => v !== null && typeof v === "object" && !Array.isArray(v));
}

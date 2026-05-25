"use client";

import { useState } from "react";
import {
  BookOpen,
  Check,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  Loader2,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Tooltip } from "@/components/ui/Tooltip";
import { useToast } from "@/components/providers/ToastProvider";
import { cn } from "@/lib/utils/cn";
import {
  DOCS_CONCEPTS_URL,
  DOCS_INTEGRATIONS_URL,
  DOCS_MANUAL_URL,
} from "@/lib/utils/constants";

/* ── Step section wrapper ─────────────────────────────────────────────── */

interface StepSectionProps {
  number: number;
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}

export function StepSection({
  number,
  icon,
  title,
  description,
  children,
}: StepSectionProps) {
  return (
    <section className="space-y-3">
      <div className="flex items-start gap-3">
        <span className="flex-shrink-0 flex items-center justify-center h-7 w-7 border border-border bg-surface-hi text-xs font-mono text-text-dim">
          {String(number).padStart(2, "0")}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-text-muted">{icon}</span>
            <h2 className="text-sm font-mono text-text">{title}</h2>
          </div>
          <p className="text-xs font-mono text-text-muted mt-1 leading-relaxed">
            {description}
          </p>
        </div>
      </div>
      <div className="pl-10 space-y-2">{children}</div>
    </section>
  );
}

/* ── Generic option tabs ──────────────────────────────────────────────── */

export function ProviderTabs<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { id: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex items-center gap-0 border border-border bg-surface-hi w-fit">
      {options.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => onChange(p.id)}
          className={cn(
            "px-3 py-1.5 text-xs font-mono transition-colors border-r border-border last:border-r-0",
            value === p.id
              ? "bg-surface text-primary"
              : "text-text-dim hover:text-text",
          )}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

/* ── One-click API key creator ────────────────────────────────────────── */

export function CreateApiKeyButton({
  loading,
  onClick,
}: {
  loading: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1.5 border text-xs font-mono transition-colors",
        "border-info/40 bg-info/10 text-info hover:bg-info/20",
        "disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:bg-info/10",
      )}
    >
      {loading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Plus className="h-3 w-3" />
      )}
      {loading ? "Creating API key..." : "Create API key"}
    </button>
  );
}

/* ── One-time raw-key panel ───────────────────────────────────────────── */

export function IssuedKeyPanel({
  rawKey,
  onDismiss,
}: {
  rawKey: string;
  onDismiss: () => void;
}) {
  const { toast } = useToast();
  const [showKey, setShowKey] = useState(true);
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(rawKey);
    toast({ title: "Copied to clipboard", variant: "success" });
    setCopied(true);
    setSaved(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="bg-warning/5 border border-warning/20 p-3 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-warning font-mono">
          Copy this key into{" "}
          <code className="text-text">PANDAPROBE_API_KEY </code> now. You
          won&apos;t be able to see it again.
        </p>
        <Tooltip content={saved ? "" : "Copy the key before dismissing"}>
          <span>
            <Button size="sm" disabled={!saved} onClick={onDismiss}>
              Done
            </Button>
          </span>
        </Tooltip>
      </div>
      <div className="flex items-center gap-2">
        <code className="ph-no-capture flex-1 text-xs font-mono text-text bg-bg px-2 py-2 border border-border overflow-x-auto whitespace-nowrap scrollbar-hide">
          {showKey ? rawKey : "••••••••••••••••"}
        </code>
        <Tooltip content="Toggle visibility">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowKey(!showKey)}
          >
            {showKey ? (
              <EyeOff className="h-3 w-3" />
            ) : (
              <Eye className="h-3 w-3" />
            )}
          </Button>
        </Tooltip>
        <Tooltip content={copied ? "Copied!" : "Copy"}>
          <Button variant="ghost" size="icon" onClick={handleCopy}>
            {copied ? (
              <Check className="h-3 w-3 text-success" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
          </Button>
        </Tooltip>
      </div>
    </div>
  );
}

/* ── Next steps ───────────────────────────────────────────────────────── */

export function NextSteps() {
  const links = [
    {
      title: "Concepts",
      description:
        "Traces, spans, sessions, and how the data model fits together.",
      href: DOCS_CONCEPTS_URL,
    },
    {
      title: "Integrations",
      description:
        "Advance integrations for frameworks like LangGraph, CrewAI, Google ADK, Claude Agent SDK, and OpenAI Agents.",
      href: DOCS_INTEGRATIONS_URL,
    },
    {
      title: "Manual Instrumentation",
      description:
        "Full control with @trace and @span decorators for custom span names, kinds, and metadata.",
      href: DOCS_MANUAL_URL,
    },
  ];

  return (
    <section className="space-y-3 pt-4 border-t border-border">
      <div className="flex items-center gap-2">
        <BookOpen className="h-4 w-4 text-text-muted" />
        <h2 className="text-sm font-mono text-text">Explore the docs</h2>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {links.map((link) => (
          <a
            key={link.title}
            href={link.href}
            target="_blank"
            rel="noopener noreferrer"
            className="group block border-engraved bg-surface p-3 hover:bg-surface-hi transition-colors"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-mono text-primary">
                {link.title}
              </span>
              <ExternalLink className="h-3 w-3 text-text-muted group-hover:text-text transition-colors" />
            </div>
            <p className="text-[11px] font-mono text-text-muted mt-1.5 leading-relaxed">
              {link.description}
            </p>
          </a>
        ))}
      </div>
    </section>
  );
}

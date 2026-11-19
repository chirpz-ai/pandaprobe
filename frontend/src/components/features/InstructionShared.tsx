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
import type { SdkLanguage } from "@/components/config/quickstart-examples";

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
      <div className="min-w-0 space-y-2 sm:pl-10">{children}</div>
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
    <div className="flex max-w-full items-center overflow-x-auto border border-border bg-surface-hi w-fit">
      {options.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => onChange(p.id)}
          aria-pressed={value === p.id}
          className={cn(
            "shrink-0 whitespace-nowrap px-3 py-1.5 text-xs font-mono transition-colors border-r border-border last:border-r-0 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary",
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

export function SdkLanguageTabs({
  value,
  onChange,
  typescriptOnly = false,
}: {
  value: SdkLanguage;
  onChange: (language: SdkLanguage) => void;
  typescriptOnly?: boolean;
}) {
  if (typescriptOnly) {
    return <p className="text-xs text-text-dim">TypeScript only</p>;
  }
  return (
    <ProviderTabs
      options={[
        { id: "python", label: "Python" },
        { id: "typescript", label: "TypeScript" },
      ]}
      value={value}
      onChange={onChange}
    />
  );
}

export function QuickstartRunHint({ language }: { language: SdkLanguage }) {
  return (
    <p className="text-xs text-text-muted leading-relaxed">
      {language === "python"
        ? "Save as quickstart.py and run python quickstart.py in the terminal where you set the environment variables."
        : "Save as quickstart.mts and run npx tsx quickstart.mts in the terminal where you set the environment variables. Use Node.js with the versions required by your framework and provider packages."}
    </p>
  );
}

export function QuickstartDocsLink({ href }: { href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 text-xs text-text-dim hover:text-primary"
    >
      Open full guide
      <ExternalLink aria-hidden="true" className="h-3 w-3" />
    </a>
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
        "Framework guides for LangGraph, DeepAgents, Vercel AI, and more.",
      href: DOCS_INTEGRATIONS_URL,
    },
    {
      title: "Manual Instrumentation",
      description:
        "Add custom tracing in Python or TypeScript with explicit trace and span boundaries.",
      href: DOCS_MANUAL_URL,
    },
  ];

  return (
    <section className="space-y-3 pt-4 border-t border-divider">
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
            <p className="text-caption font-mono text-text-muted mt-1.5 leading-relaxed">
              {link.description}
            </p>
          </a>
        ))}
      </div>
    </section>
  );
}

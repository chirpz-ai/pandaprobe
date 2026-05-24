"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  Package,
  Plus,
  Settings2,
  Terminal,
  Zap,
} from "lucide-react";
import { useProject } from "@/components/providers/ProjectProvider";
import { useOrgId, useProjectId, useProjectPath } from "@/hooks/useNavigation";
import { createAPIKey } from "@/lib/api/api-keys";
import { extractErrorMessage } from "@/lib/api/client";
import { KeyExpiration } from "@/lib/api/enums";
import { listTraces } from "@/lib/api/traces";
import { queryKeys } from "@/lib/query/keys";
import {
  API_URL,
  DOCS_TRACING_URL,
  DOCS_INTEGRATIONS_URL,
  DOCS_MANUAL_URL,
  DOCS_CONCEPTS_URL,
} from "@/lib/utils/constants";
import { CodeBlock } from "@/components/common/CodeBlock";
import { Button } from "@/components/ui/Button";
import { Tooltip } from "@/components/ui/Tooltip";
import { useToast } from "@/components/providers/ToastProvider";
import { cn } from "@/lib/utils/cn";

/* ── SDK snippets ─────────────────────────────────────────────────────── */

const INSTALL_SNIPPETS = {
  openai: 'pip install "pandaprobe[openai]"',
  anthropic: 'pip install "pandaprobe[anthropic]"',
  gemini: 'pip install "pandaprobe[google-genai]"',
};

const PROVIDER_KEY_EXPORTS: Record<Provider, string> = {
  openai: 'export OPENAI_API_KEY="your-openai-key"',
  anthropic: 'export ANTHROPIC_API_KEY="your-anthropic-key"',
  gemini: 'export GOOGLE_API_KEY="your-google-key"',
};

function envSnippet(provider: Provider, projectName: string, endpoint: string) {
  return `export PANDAPROBE_API_KEY="your-api-key"
export PANDAPROBE_PROJECT_NAME="${projectName}"
export PANDAPROBE_ENDPOINT="${endpoint}"

${PROVIDER_KEY_EXPORTS[provider]}`;
}

const WRAP_SNIPPETS = {
  openai: `from pandaprobe.wrappers import wrap_openai
from openai import OpenAI

client = wrap_openai(OpenAI())

response = client.chat.completions.create(
    model="gpt-5.4",
    messages=[{"role": "user", "content": "What is agent engineering?"}],
)

print(response.choices[0].message.content)`,
  anthropic: `from pandaprobe.wrappers import wrap_anthropic
from anthropic import Anthropic

client = wrap_anthropic(Anthropic())

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "What is agent engineering?"}],
)

print(response.content[0].text)`,
  gemini: `from pandaprobe.wrappers import wrap_gemini
from google import genai

client = wrap_gemini(genai.Client())

response = client.models.generate_content(
    model="gemini-3.1-flash-preview",
    contents="What is agent engineering?",
)

print(response.text)`,
};

type Provider = keyof typeof INSTALL_SNIPPETS;

const PROVIDERS: { id: Provider; label: string }[] = [
  { id: "openai", label: "OpenAI" },
  { id: "anthropic", label: "Anthropic" },
  { id: "gemini", label: "Google Gemini" },
];

/* ── Body ─────────────────────────────────────────────────────────────── */

export function InstructionTraceQuickstart() {
  const { currentProject } = useProject();
  const basePath = useProjectPath();
  const orgId = useOrgId();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [provider, setProvider] = useState<Provider>("openai");
  const [issuedKey, setIssuedKey] = useState<string | null>(null);
  const [creatingKey, setCreatingKey] = useState(false);

  const projectName = currentProject?.name ?? "my-first-project";

  async function handleCreateKey() {
    if (creatingKey) return;
    setCreatingKey(true);
    try {
      const result = await createAPIKey(orgId, {
        name: "Quickstart",
        expiration: KeyExpiration.never,
      });
      if (!result.raw_key) {
        toast({ title: "Key returned without raw value", variant: "error" });
        return;
      }
      setIssuedKey(result.raw_key);
      queryClient.invalidateQueries({
        queryKey: queryKeys.apiKeys.list(orgId),
      });
      toast({ title: "API key created", variant: "success" });
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setCreatingKey(false);
    }
  }

  return (
    <>
      <StepSection
        number={1}
        icon={<KeyRound className="h-4 w-4" />}
        title="Create your API key"
        description="Generate a key to authenticate the SDK."
      >
        {issuedKey ? (
          <IssuedKeyPanel
            rawKey={issuedKey}
            onDismiss={() => setIssuedKey(null)}
          />
        ) : (
          <CreateApiKeyButton
            loading={creatingKey}
            onClick={handleCreateKey}
          />
        )}
      </StepSection>

      <StepSection
        number={2}
        icon={<Package className="h-4 w-4" />}
        title="Install the SDK"
        description="Pick the LLM provider you want to trace. You can add more later."
      >
        <ProviderTabs value={provider} onChange={setProvider} />
        <CodeBlock code={INSTALL_SNIPPETS[provider]} language="bash" />
      </StepSection>

      <StepSection
        number={3}
        icon={<Settings2 className="h-4 w-4" />}
        title="Set environment variables"
        description="Point the SDK at your project and paste the API key you just created."
      >
        <CodeBlock
          code={envSnippet(provider, projectName, API_URL)}
          language="bash"
        />
      </StepSection>

      <StepSection
        number={4}
        icon={<Terminal className="h-4 w-4" />}
        title="Wrap your LLM client"
        description="One line of instrumentation. Every call gets a trace automatically."
      >
        <ProviderTabs value={provider} onChange={setProvider} />
        <CodeBlock code={WRAP_SNIPPETS[provider]} language="python" />
        <DocsHint />
      </StepSection>

      <StepSection
        number={5}
        icon={<Zap className="h-4 w-4" />}
        title="View your first trace"
        description="Run your script, then come back here to confirm it landed."
      >
        <TraceDetector basePath={basePath} />
      </StepSection>

      <NextSteps />
    </>
  );
}

/* ── Step section wrapper ─────────────────────────────────────────────── */

interface StepSectionProps {
  number: number;
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}

function StepSection({
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

/* ── Provider tabs ────────────────────────────────────────────────────── */

function ProviderTabs({
  value,
  onChange,
}: {
  value: Provider;
  onChange: (p: Provider) => void;
}) {
  return (
    <div className="flex items-center gap-0 border border-border bg-surface-hi w-fit">
      {PROVIDERS.map((p) => (
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

/* ── One-click API key creator (step 1) ───────────────────────────────── */

function CreateApiKeyButton({
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

/* ── One-time raw-key panel (step 1) ──────────────────────────────────── */

function IssuedKeyPanel({
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

/* ── Docs hint (step 4) ───────────────────────────────────────────────── */

function DocsHint() {
  return (
    <div className="flex items-center gap-2 px-3 py-2 border border-border bg-surface text-xs font-mono text-text-dim">
      <BookOpen className="h-3.5 w-3.5 text-text-muted" />
      <span>Need the full walkthrough or advanced integrations?</span>
      <a
        href={DOCS_TRACING_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1 text-primary hover:text-text transition-colors"
      >
        Open documentation
        <ExternalLink className="h-3 w-3" />
      </a>
    </div>
  );
}

/* ── Trace detector (step 5) ──────────────────────────────────────────── */

function TraceDetector({ basePath }: { basePath: string }) {
  const projectId = useProjectId() ?? "";

  // One-shot check on mount. Refetches automatically when the user returns
  const tracesQuery = useQuery({
    queryKey: [
      ...queryKeys.traces.list(projectId, { limit: 1 }),
      "quickstart-detector",
    ],
    queryFn: () => listTraces({ limit: 1 }),
    staleTime: 0,
  });

  const hasTrace = (tracesQuery.data?.total ?? 0) > 0;

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 px-4 py-3 border transition-colors",
        hasTrace
          ? "border-success/40 bg-success/10"
          : "border-border bg-surface",
      )}
    >
      <div className="flex items-center gap-3 min-w-0">
        {hasTrace ? (
          <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-success" />
        ) : (
          <LiveDot />
        )}
        <span className="text-xs font-mono text-text">
          {hasTrace ? "First trace received." : "Waiting for your first trace"}
        </span>
      </div>
      <Link
        href={`${basePath}/traces`}
        className={cn(
          "flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono transition-colors border",
          hasTrace
            ? "border-success/40 bg-success/20 text-success hover:bg-success/30"
            : "border-primary/40 bg-primary/10 text-primary hover:bg-primary/20",
        )}
      >
        Open Traces
        <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

function LiveDot() {
  return (
    <span className="relative flex items-center justify-center h-4 w-4 flex-shrink-0">
      <span className="absolute inline-flex h-2 w-2 rounded-full bg-primary opacity-60 animate-ping" />
      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
    </span>
  );
}

/* ── Next steps ───────────────────────────────────────────────────────── */

function NextSteps() {
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

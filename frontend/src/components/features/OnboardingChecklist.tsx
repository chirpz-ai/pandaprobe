"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import {
  Check,
  KeyRound,
  Rocket,
  ArrowRight,
  BookOpen,
  ExternalLink,
} from "lucide-react";
import { useOnboardingStatus } from "@/hooks/useOnboardingStatus";
import { DOCS_QUICKSTART_URL } from "@/lib/utils/constants";
import { cn } from "@/lib/utils/cn";

export function OnboardingChecklist() {
  const {
    apiKeyCreated,
    traceIngested,
    allComplete,
    isLoading,
    projectId,
    orgId,
  } = useOnboardingStatus();

  if (isLoading) return null;
  if (allComplete) return null;

  const orgBase = `/org/${orgId}`;
  const projectBase = projectId ? `${orgBase}/project/${projectId}` : null;

  const completedCount = [apiKeyCreated, traceIngested].filter(Boolean).length;

  const steps: OnboardingStepProps[] = [
    {
      index: 1,
      title: "Create an API key",
      description:
        "Your API key authenticates the SDK so it can ship traces to PandaProbe. Store it securely.",
      icon: <KeyRound className="h-4 w-4" />,
      done: apiKeyCreated,
      cta: {
        label: apiKeyCreated ? "Manage API keys" : "Create API key",
        href: `${orgBase}/settings/api-keys`,
      },
    },
    {
      index: 2,
      title: "Send your first trace",
      description:
        "Install the SDK, wrap your LLM or use agent integrations, and run your application. Your first trace will show up in seconds.",
      icon: <Rocket className="h-4 w-4" />,
      done: traceIngested,
      cta: {
        label: traceIngested ? "View traces" : "Open Quickstart",
        href: traceIngested
          ? `${projectBase}/traces`
          : projectBase
            ? `${projectBase}/quickstart`
            : `${orgBase}/quickstart`,
      },
      disabled: !apiKeyCreated,
      disabledReason: "Create an API key first",
    },
  ];

  return (
    <section
      className="border-engraved bg-surface animate-fade-in max-w-3xl mx-auto"
      aria-label="Onboarding checklist"
    >
      <header className="flex items-center justify-between gap-4 px-5 py-3 border-b border-border">
        <p className="text-xs font-mono text-text-dim min-w-0">
          Two short steps to your first trace. We&apos;ll check each one off as
          you go.
        </p>
        <span className="flex-shrink-0 px-2 py-0.5 border border-border bg-surface-hi text-[10px] font-mono uppercase tracking-wider text-text-dim">
          {completedCount}/2 done
        </span>
      </header>

      <ol>
        {steps.map((step, i) => (
          <OnboardingStep key={step.index} {...step} withTopBorder={i > 0} />
        ))}
      </ol>

      <footer className="flex items-center justify-between gap-3 px-5 py-2.5 border-t border-border bg-surface-hi">
        <span className="flex items-center gap-2 text-xs font-mono text-text-dim">
          <BookOpen className="h-3.5 w-3.5" />
          Need the full walkthrough?
        </span>
        <a
          href={DOCS_QUICKSTART_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs font-mono text-text hover:text-primary transition-colors"
        >
          Open documentation
          <ExternalLink className="h-3 w-3" />
        </a>
      </footer>
    </section>
  );
}

interface OnboardingStepProps {
  index: number;
  title: string;
  description: string;
  icon: ReactNode;
  done: boolean;
  cta: { label: string; href: string };
  disabled?: boolean;
  disabledReason?: string;
}

function OnboardingStep({
  index,
  title,
  description,
  icon,
  done,
  cta,
  disabled,
  disabledReason,
  withTopBorder,
}: OnboardingStepProps & { withTopBorder: boolean }) {
  return (
    <li
      className={cn(
        "flex items-center gap-3 px-5 py-3 transition-colors",
        withTopBorder && "border-t border-border",
      )}
    >
      <StepBadge index={index} done={done} />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-text-muted">{icon}</span>
          <h3
            className={cn(
              "text-sm font-mono",
              done ? "text-text-dim line-through" : "text-text",
            )}
          >
            {title}
          </h3>
        </div>
        <p className="text-xs font-mono text-text-muted mt-0.5 leading-snug">
          {description}
        </p>
      </div>

      <div className="flex-shrink-0">
        {disabled ? (
          <span
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-border bg-surface-hi text-xs font-mono text-text-muted cursor-not-allowed"
            title={disabledReason}
          >
            {cta.label}
          </span>
        ) : done ? (
          <Link
            href={cta.href}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-border bg-surface text-xs font-mono text-text-dim hover:text-text hover:border-primary/40 transition-colors"
          >
            {cta.label}
            <ArrowRight className="h-3 w-3" />
          </Link>
        ) : (
          <Link
            href={cta.href}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-info/40 bg-info/10 text-xs font-mono text-info hover:bg-info/20 transition-colors"
          >
            {cta.label}
            <ArrowRight className="h-3 w-3" />
          </Link>
        )}
      </div>
    </li>
  );
}

function StepBadge({ index, done }: { index: number; done: boolean }) {
  if (done) {
    return (
      <span className="flex-shrink-0 flex items-center justify-center h-7 w-7 border border-success/40 bg-success/10 text-success">
        <Check className="h-3.5 w-3.5" />
      </span>
    );
  }
  return (
    <span className="flex-shrink-0 flex items-center justify-center h-7 w-7 border border-border bg-surface-hi text-xs font-mono text-text-dim">
      {String(index).padStart(2, "0")}
    </span>
  );
}

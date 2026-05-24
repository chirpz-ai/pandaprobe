"use client";

import { BookOpen, ExternalLink, Route, Settings2, Users } from "lucide-react";
import {
  DOCS_EVAL_API_URL,
  DOCS_EVAL_SCHEDULING_URL,
  DOCS_EVAL_UI_URL,
} from "@/lib/utils/constants";
import { cn } from "@/lib/utils/cn";
import { StepSection } from "./InstructionShared";

/* ── Assets — place files in frontend/public/assets/evals/ ────────────── */

const TRACE_EVAL_VIDEO = "/assets/traces-eval.mp4";
const SESSION_EVAL_VIDEO = "/assets/session-eval.mp4";

/* ── Timeline step data ───────────────────────────────────────────────── */

const TRACE_EVAL_STEPS = [
  {
    title: "Open the Traces tab",
    description:
      "In the PandaProbe dashboard, open Traces to view the trace table.",
  },
  {
    title: "Choose traces to evaluate",
    description:
      "Select a batch of traces from the table and click Evaluate, or open a specific trace and click Evaluate from the detail view.",
  },
  {
    title: "Configure the eval run",
    description:
      "Enter a run name, select one or more trace-level metrics, and optionally choose the model used for LLM-as-judge evaluation.",
  },
  {
    title: "Submit the run",
    description:
      "Click Submit. PandaProbe starts the eval run in the background and reports the scores.",
  },
];

const SESSION_EVAL_STEPS = [
  {
    title: "Open the Sessions tab",
    description:
      "Open Sessions to view grouped agent traces representing a single agent lifecycle.",
  },
  {
    title: "Choose sessions to evaluate",
    description:
      "Select a batch of sessions from the table, or open one session and click Evaluate.",
  },
  {
    title: "Configure the eval run",
    description: "Enter a run name and select session-level metrics.",
  },
  {
    title: "Customize signal weights",
    description:
      "Optionally adjust how much each trace-level signal contributes to the session score.",
  },
  {
    title: "Submit the run",
    description:
      "Click Submit. PandaProbe starts the session eval run in the background and reports the scores.",
  },
];

/* ── Body ─────────────────────────────────────────────────────────────── */

export function InstructionEvalQuickstart() {
  return (
    <>
      <StepSection
        number={1}
        icon={<Route className="h-4 w-4" />}
        title="Evaluate traces"
        description="Evaluate individual traces by selecting them directly from the Traces table."
      >
        <div className="border border-border bg-surface p-3">
          <Timeline steps={TRACE_EVAL_STEPS} />
        </div>
        <video
          controls
          preload="metadata"
          playsInline
          className="w-full block border border-border bg-surface-hi"
        >
          <source src={TRACE_EVAL_VIDEO} type="video/mp4" />
        </video>
      </StepSection>

      <StepSection
        number={2}
        icon={<Users className="h-4 w-4" />}
        title="Evaluate sessions"
        description="Evaluate complete agent lifecycles by selecting sessions."
      >
        <div className="border border-border bg-surface p-3">
          <Timeline steps={SESSION_EVAL_STEPS} />
        </div>
        <video
          controls
          preload="metadata"
          playsInline
          className="w-full block border border-border bg-surface-hi"
        >
          <source src={SESSION_EVAL_VIDEO} type="video/mp4" />
        </video>
      </StepSection>

      <StepSection
        number={3}
        icon={<Settings2 className="h-4 w-4" />}
        title="Advanced evaluation & monitoring"
        description="Go further with filtered eval runs, API-driven evaluation, and automated monitors."
      >
        <div className="border border-border bg-surface p-3">
          <p className="text-xs font-mono text-text-muted leading-relaxed">
            The steps above cover basic interactive evaluation from the Traces
            and Sessions tabs. PandaProbe also supports creating evaluation runs
            with filters and sampling from the Evaluations tab, running
            evaluations programmatically via the API, and scheduling recurring
            monitors. Explore the links below to learn more.
          </p>
        </div>
      </StepSection>

      <EvalNextSteps />
    </>
  );
}

/* ── Timeline ─────────────────────────────────────────────────────────── */

interface TimelineStep {
  title: string;
  description: string;
}

function Timeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <div className="relative">
      {steps.map((step, i) => (
        <div key={step.title} className="flex gap-3 relative">
          {i < steps.length - 1 && (
            <div className="absolute left-[10px] top-[22px] bottom-0 w-px bg-border" />
          )}
          <span className="relative z-10 flex-shrink-0 flex items-center justify-center h-[22px] w-[22px] border border-border bg-surface-hi text-[10px] font-mono text-text-dim">
            {i + 1}
          </span>
          <div
            className={cn("flex-1 min-w-0", i < steps.length - 1 ? "pb-3" : "")}
          >
            <p className="text-xs font-mono text-text leading-relaxed">
              {step.title}
            </p>
            <p className="text-[11px] font-mono text-text-muted mt-0.5 leading-relaxed">
              {step.description}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Next steps ───────────────────────────────────────────────────────── */

function EvalNextSteps() {
  const links = [
    {
      title: "Trace & Session Eval Runs",
      description:
        "Filtered runs, sampling, and advanced setup from the Evaluations tab.",
      href: DOCS_EVAL_UI_URL,
    },
    {
      title: "Run via API",
      description:
        "Create eval runs programmatically from CI, notebooks, or internal tools.",
      href: DOCS_EVAL_API_URL,
    },
    {
      title: "Scheduled Monitors",
      description:
        "Automate recurring evaluations on a daily, weekly, or custom cadence.",
      href: DOCS_EVAL_SCHEDULING_URL,
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

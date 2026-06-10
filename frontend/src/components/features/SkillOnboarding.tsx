"use client";

import { useState } from "react";
import { Bot, Check, ChevronRight, Copy, Terminal } from "lucide-react";
import { useToast } from "@/components/providers/ToastProvider";
import { cn } from "@/lib/utils/cn";

type Mode = "terminal" | "agent";

const SKILL_INSTALL_COMMAND =
  "npx skills add chirpz-ai/pandaprobe-skills --skill '*' --yes";

const CODING_AGENT_PROMPT = `Help me set up and get started with PandaProbe by Chirpz AI.

First install the SKILL via \`npx skills add chirpz-ai/pandaprobe-skills --skill '*' --yes\`, and load the skill.

Then tell me what I can do with PandaProbe and use the \`setup\` path to onboard me following the interactive mode.`;

interface ModeConfig {
  label: string;
  icon: typeof Terminal;
  display: string;
  copy: string;
  toast: string;
}

const MODES: Record<Mode, ModeConfig> = {
  terminal: {
    label: "Terminal",
    icon: Terminal,
    display: "npx skills add chirpz-ai/pandaprobe-skills",
    copy: SKILL_INSTALL_COMMAND,
    toast: "Install command copied",
  },
  agent: {
    label: "Coding Agent",
    icon: Bot,
    display: "copy onboarding prompt for your coding agent",
    copy: CODING_AGENT_PROMPT,
    toast: "Onboarding prompt copied",
  },
};

const MODE_ORDER: Mode[] = ["agent", "terminal"];

export function SkillOnboarding() {
  const { toast } = useToast();
  const [mode, setMode] = useState<Mode>("agent");
  const [copied, setCopied] = useState(false);

  const active = MODES[mode];

  function handleCopy() {
    navigator.clipboard.writeText(active.copy);
    toast({ title: active.toast, variant: "success" });
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {MODE_ORDER.map((id) => {
            const { label, icon: Icon } = MODES[id];
            const isActive = id === mode;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setMode(id)}
                aria-pressed={isActive}
                className={cn(
                  "inline-flex items-center gap-2 px-3 py-1.5 border text-xs font-mono uppercase tracking-wider transition-colors",
                  isActive
                    ? "border-text text-text bg-surface-hi"
                    : "border-border text-text-dim hover:text-text hover:border-border-hi",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex items-center gap-3 border border-info/30 bg-info/10 px-4 py-3.5">
        <ChevronRight className="h-4 w-4 flex-shrink-0 text-info" />
        <code className="flex-1 min-w-0 truncate font-mono text-sm text-text">
          {active.display}
        </code>
        <button
          type="button"
          onClick={handleCopy}
          aria-label="Copy to clipboard"
          className="flex-shrink-0 p-1.5 border border-primary/50 bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-success" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </button>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { Bot, Check, ChevronRight, Copy, Terminal } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/providers/ToastProvider";
import { cn } from "@/lib/utils/cn";

type Mode = "terminal" | "agent";

const SKILL_INSTALL_COMMAND =
  "npx skills add chirpz-ai/pandaprobe-skills --skill '*' --yes";

const CODING_AGENT_PROMPT = `Help me set up and get started with PandaProbe by Chirpz AI.

First install the SKILL via \`npx skills add chirpz-ai/pandaprobe-skills --skill '*' --yes\`, and load the skill.

Then walk me through what I can do with PandaProbe and use the \`setup\` path to onboard me following the interactive mode.`;

interface ModeConfig {
  label: string;
  icon: typeof Terminal;
  display: string;
  copy: string;
  toast: string;
}

const MODES: Record<Mode, ModeConfig> = {
  terminal: {
    label: "Install Skill",
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
              <Button
                key={id}
                variant="ghost"
                size="sm"
                onClick={() => setMode(id)}
                aria-pressed={isActive}
                className={cn(
                  "border uppercase tracking-wider",
                  isActive
                    ? "border-text text-text bg-surface-hi"
                    : "border-border hover:border-border-hi",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </Button>
            );
          })}
        </div>
      </div>

      <div className="flex items-center gap-3 border border-border-hi bg-surface px-4 py-2.5">
        <ChevronRight className="h-4 w-4 flex-shrink-0 text-text-dim" />
        <code className="flex-1 min-w-0 truncate font-mono text-sm text-text">
          {active.display}
        </code>
        <Button
          variant="primary"
          size="sm"
          onClick={handleCopy}
          className="flex-shrink-0"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-success" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
          Copy
        </Button>
      </div>
    </div>
  );
}

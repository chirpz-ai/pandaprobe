"use client";

import type { ComponentType } from "react";
import { Bot, DraftingCompass, Route, type LucideIcon } from "lucide-react";
import { InstructionAgentQuickstart } from "./InstructionAgentQuickstart";
import { InstructionEvalQuickstart } from "./InstructionEvalQuickstart";
import { InstructionTraceQuickstart } from "./InstructionTraceQuickstart";

/* ── Registry ─────────────────────────────────────────────────────────── */
export type InstructionId =
  | "quickstart"
  | "agent-quickstart"
  | "evaluation-quickstart";

export interface InstructionDefinition {
  id: InstructionId;
  title: string;
  description: string;
  icon: LucideIcon;
  Body: ComponentType;
}

export const INSTRUCTIONS: Record<InstructionId, InstructionDefinition> = {
  quickstart: {
    id: "quickstart",
    title: "Trace Quickstart",
    description: "Trace your first LLM call in under 2 minutes.",
    icon: Route,
    Body: InstructionTraceQuickstart,
  },
  "agent-quickstart": {
    id: "agent-quickstart",
    title: "Agent Quickstart",
    description: "Instrument agent frameworks end-to-end.",
    icon: Bot,
    Body: InstructionAgentQuickstart,
  },
  "evaluation-quickstart": {
    id: "evaluation-quickstart",
    title: "Evaluation Quickstart",
    description: "Evaluate your agent's traces and sessions.",
    icon: DraftingCompass,
    Body: InstructionEvalQuickstart,
  },
};

export function getInstruction(id: InstructionId): InstructionDefinition {
  return INSTRUCTIONS[id];
}

/* ── Dispatcher ───────────────────────────────────────────────────────── */

interface InstructionContentProps {
  instructionId: InstructionId;
}

export function InstructionContent({ instructionId }: InstructionContentProps) {
  const { Body } = getInstruction(instructionId);
  return (
    <div className="animate-fade-in space-y-6 pb-6">
      <Body />
    </div>
  );
}

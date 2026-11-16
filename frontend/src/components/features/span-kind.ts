import {
  Bot,
  Wrench,
  Sparkles,
  Search,
  Link,
  Grid3X3,
  Circle,
  Activity,
} from "lucide-react";

/** One stable color per kind, shared by Waterfall and Timeline. */
export const SPAN_KINDS = {
  AGENT: { icon: Bot, color: "var(--color-brand-green)" },
  TOOL: { icon: Wrench, color: "var(--color-brand-yellow)" },
  LLM: { icon: Sparkles, color: "var(--color-span-llm)" },
  RETRIEVER: { icon: Search, color: "var(--color-span-retriever)" },
  CHAIN: { icon: Link, color: "var(--color-span-chain)" },
  EMBEDDING: { icon: Grid3X3, color: "var(--color-span-embedding)" },
  OTHER: { icon: Circle, color: "var(--color-text-muted)" },
  TRACE: { icon: Activity, color: "var(--color-brand-blue)" },
};

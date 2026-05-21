export const PROVIDER_MODELS: Record<string, string[]> = {
  vertex_ai: ["vertex_ai/gemini-3.1-flash-lite", "vertex_ai/gemini-3.5-flash"],
  google_genai: ["gemini/gemini-3.1-flash-lite"],
  openai: ["gpt-5-mini"],
  anthropic: ["claude-sonnet-4-6"],
};

export const DEFAULT_SIGNAL_WEIGHTS: Record<string, number> = {
  confidence: 1.0,
  loop_detection: 1.0,
  tool_correctness: 0.8,
  coherence: 1.0,
};

// Markdown copied by the dashboard's Coding Agent onboarding option.
export const CODING_AGENT_PROMPT = `# You are onboarding this project to PandaProbe

PandaProbe is an open-source platform for tracing, evaluating, and improving AI agents. Its Python and TypeScript SDKs connect to your existing agent, model providers, and tools. The product has three layers: Trace records what happened, Evaluate measures whether it worked, and Reflect helps the agent turn mistakes into reusable guidance.

Reflect gives the agent a persistent rule filesystem and feedback from evaluated failures. The agent proposes changes to its guidance; independent validation decides which changes become shared rules for future runs. It does not automatically accept its own advice or guarantee future success.

## What you can add

| Capability | What it provides | Use when |
|---|---|---|
| Trace | Execution timelines with model calls, tool calls, inputs, outputs, errors, and usage | Understand or debug an agent run |
| Sessions | Related traces grouped under one session ID | Follow a conversation or multi-step task across runs |
| Evaluate | Trace and session metrics, plus programmatic trace scores | Measure task quality and identify failures |
| Reflect | Failure feedback, working memory, and independently validated rules | Help an agent learn from recurring mistakes |

A trace represents an execution; spans represent the work inside it. Sessions group related executions. Traces and evaluations belong to a project within your PandaProbe organization. Reflect also uses a durable workspace to store rules and validation history.

Start by making one existing agent observable. Add Evaluate and Reflect according to the project's needs.

## Step 1: Find the right integration

Identify the agent entry point, language, framework, and model provider. Explain briefly where PandaProbe fits in this project, using concrete files and the table below.

| Existing code | Integration approach |
|---|---|
| LangChain, LangGraph, DeepAgents, or OpenAI Agents SDK | Use the framework's PandaProbe tracing integration |
| Claude Agent SDK | Use the Python adapter or TypeScript query wrapper |
| Google ADK or CrewAI | Use the Python framework integration |
| Vercel AI SDK | Use the TypeScript middleware |
| Direct model-provider calls | Wrap the existing provider client |
| Custom agent loop or application tools | Use manual tracing for work not already captured |

If there are multiple agents, ask which one to start with. If there is no agent code, describe two or three concrete uses for PandaProbe in the intended application and ask which to build.

Documentation index: https://docs.pandaprobe.com/llms.txt
Framework integrations: https://docs.pandaprobe.com/tracing/integrations/overview
Provider wrappers: https://docs.pandaprobe.com/tracing/wrappers/overview
SDK reference: https://docs.pandaprobe.com/reference/overview

Read the matching integration guide before implementing. Use its language-specific APIs and check compatibility with the installed SDK. Python and TypeScript do not have identical framework coverage or signatures.

## Step 2: Connect to PandaProbe

Use an account and API key from https://app.pandaprobe.com, or the user's self-hosted deployment.

Required environment variables:
- \`PANDAPROBE_API_KEY\`: the organization's API key.
- \`PANDAPROBE_PROJECT_NAME\`: the project that should receive this agent's traces.
- \`PANDAPROBE_ENDPOINT\`: the API base URL, only when overriding the hosted endpoint.

Keep the agent's existing model-provider credentials. Store keys in server-side environment configuration; never hardcode or print them. If the PandaProbe key or project name is missing, ask the user to configure it locally. Continue with integration code, but wait for credentials before attempting a live run.

Install the \`pandaprobe\` package using the project's package manager. Add only the provider or framework dependencies required by the chosen integration. Python offers optional extras; TypeScript uses separate optional dependencies.

Installation: https://docs.pandaprobe.com/tracing/get-started/installation

## Step 3: Trace a real agent execution

Attach the integration to the existing agent. Keep its model, prompts, tools, and application behavior. Prefer framework instrumentation over separately wrapping calls it already captures. Add manual spans only for missing custom work, and attach a session ID when runs belong to one conversation or task.

Run a small example with synthetic input through the instrumented entry point. Flush pending traces before a short-lived process exits: \`pandaprobe.flush()\` in Python or \`await flush()\` in TypeScript when using the default client. Follow the documented lifecycle for explicit clients and long-running services.

Confirm the trace appears in the intended project and inspect its span hierarchy, inputs, outputs, and errors. Show the user the trace ID or dashboard link and explain what is now visible. If a live run is blocked, state what remains unverified.

Tracing quickstart: https://docs.pandaprobe.com/tracing/get-started/quickstart

## Step 4: Choose what success means

Recommend a small evaluation suited to this agent's task. Use trace metrics for individual executions and session metrics for behavior across related runs. If the application already has a deterministic check or an external outcome signal, consider recording it as a programmatic trace score.

Explain the selected metrics and judge-model requirements. Run the evaluation when the user wants it enabled, then inspect completed scores and explanations. A queued evaluation is not a result. Recurring monitors are a separate choice.

Evaluation quickstart: https://docs.pandaprobe.com/evaluation/get-started/quickstart
Programmatic scoring: https://docs.pandaprobe.com/evaluation/types/scoring

## Step 5: Add reflection where it is useful

For recurring failures, explain how Reflect could help this agent and ask whether to enable it. Reflect is included in the same SDK: \`pandaprobe.reflect\` in Python and \`pandaprobe/reflect\` in TypeScript.

Follow the matching framework guide to equip the host agent and run it through an explicit Reflect execution boundary. Reuse its tracing client. Native integrations supply the \`reflect_bash\` filesystem tool; the agent can search accepted rules, maintain session notes, and propose guidance at a reflection checkpoint.

Before publishing shared guidance, provide reproducible cases, fresh business state, and an independent verifier of task outcomes. Reflect compares baseline and candidate behavior before accepting a rule change. Session notes are working memory, not validated shared rules.

Reflect requires a supported filesystem/native runtime, not a browser or edge environment. If the runtime or validation setup is missing, explain what the project needs before enabling it.

Reflect quickstart: https://docs.pandaprobe.com/reflect/quickstart
Framework guides: https://docs.pandaprobe.com/reflect/integrations/overview
Rules and memory: https://docs.pandaprobe.com/reflect/rules-and-memory
Validation: https://docs.pandaprobe.com/reflect/validation

Finish by showing how to run the integrated agent, where to inspect its traces, and which evaluation or reflection capabilities are enabled.`;

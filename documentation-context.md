# PandaProbe Reflect and documentation context

Context snapshot: 2026-10-28. This records the product background, implemented behavior, documentation decisions, and source locations behind the current documentation. It is a context reference, not an implementation plan or a list of tasks.

## Product background

PandaProbe is an open-source platform for tracing, evaluating, and monitoring AI agents. Its public product stack is **Trace → Evaluate → Reflect**:

- **Trace** captures agent executions, model calls, tools, sessions, and custom application work.
- **Evaluate** measures traces and sessions through platform metrics, independent outcome signals, and programmatic scores.
- **Reflect** connects evaluation evidence to agent-authored guidance that can be independently tested and reused.

Reflect began as the experimental **PandaProbe Harness** package. The migration was both a product rename and an architectural change. The name Reflect deliberately describes the supported capability without promising automatic or permanent repair. A plausible reflection, a written rule, validation acceptance, retrieval, and later task success are separate observations.

The experimental Harness eventually used a developer-owned task agent and a package-owned managed repair agent. That separation reduced task-agent administration and isolated repair attribution, but added another agent configuration and tool loop. The released Reflect design instead lets the developer's agent retrieve guidance, maintain memory, and reflect at a bounded checkpoint. Deterministic SDK code retains evaluation scheduling, proposal bookkeeping, validation, and publication authority.

There is no retained legacy Harness API, bridge distribution, old tool-name compatibility layer, or separate Reflect package. Historical Harness code and experiments remain research artifacts; their results are not results from the released Reflect SDKs. A new comparison against the old architecture was explicitly outside this implementation's scope.

## Released SDKs and integration model

| Area | Python | TypeScript |
| --- | --- | --- |
| Distribution | Existing `pandaprobe` package | Existing `pandaprobe` npm package |
| Reflect entry point | `pandaprobe.reflect` | `pandaprobe/reflect` |
| Reusable platform API | `pandaprobe.api` | `pandaprobe/api` |
| Reflect release represented by this documentation | 0.6.0 | 0.5.0 |
| Configuration style | snake_case | camelCase |
| Baseline runtime | Python 3.10+; some frameworks require newer Python | Core SDK supports Node 18+; native Reflect examples use Node 22+ |

Python adds optional dependencies through `pandaprobe[reflect]`, composable with framework extras. TypeScript uses optional framework and native shell/locking dependencies. Exact dependencies and platform requirements are recorded in package metadata and the installation guides. The TypeScript version reproduces the Python lifecycle and validation behavior, with language-appropriate APIs and framework adapters; it is not a mechanical translation of method signatures.

The desired developer experience is a short integration with an existing traced agent. Native integrations supply `reflect_bash` automatically; developers do not choose a Bash provider or assemble many rule tools. Existing model configuration, prompts, business tools, and agent framework remain application-owned. The higher-level pattern is a Reflect runtime, an equipped agent, and an explicit `run(...)` boundary. Some Python frameworks accept existing objects, while others and the TypeScript integrations use factories. Generic asynchronous invocation callbacks cover custom loops.

Python native integrations cover LangChain, LangGraph, DeepAgents, OpenAI Agents SDK, Claude Agent SDK, Google ADK, and CrewAI. TypeScript covers LangChain, LangGraph, DeepAgents, OpenAI Agents SDK, Claude Agent SDK, and Vercel AI. Framework coverage is therefore not identical. Reflect requires filesystem/native runtime support; browser and edge execution are not part of the supported Reflect experience.

## What Reflect does

The conceptual loop is **Detect → Notify → Reflect → Validate**:

1. The application runs its task agent through an explicit execution boundary. Existing PandaProbe instrumentation produces traces; scoped trace capture associates their IDs with that execution.
2. Reflect waits for trace visibility and requests platform evaluations. Configured thresholds and trajectory signals can produce a failure notice with diagnostic evidence.
3. The same host agent receives the notice at a bounded reflection checkpoint. It can inspect evidence, search existing rules, and edit its working rule filesystem, or leave it unchanged.
4. The SDK turns the difference from the accepted baseline into a structured proposal. No change, duplicate, invalid proposal, conflict, timeout, and operational failure have distinct outcomes.
5. Host replay or deliberately paired live trials provide independently verified outcomes. The SDK decides whether evidence supports acceptance, rejection, or leaving the proposal pending.
6. Acceptance publishes an immutable rule revision. Later executions receive an accepted snapshot and can search and read its guidance through the supplied tool.

“Same agent” means reuse of the application's agent behavior and model, not a guarantee that the same object or uninterrupted conversation is used. Native adapters may clone or reconstruct objects to isolate phases. Reflection is limited to rule and memory administration in supported native adapters; custom-loop dispatch is application-owned.

`run(...)` returns the task's original result. A later reflection failure does not replace that result. Task exceptions remain task exceptions. Export, evaluation, reflection, validation, and shutdown have separate lifecycle boundaries. In particular, replay validation can need resources used by the task, so validation settlement is separate from the task barrier.

An **execution** identifies one invocation; a **session** groups related work; a **workspace** holds durable state shared by executions. Session identity is not a substitute for a unique execution ID.

## Filesystem, guidance, and active memory

The filesystem remains central to Reflect. `reflect_bash` is a real embedded Bashkit interpreter over an isolated virtual filesystem, not unrestricted access to the application's host shell. Its ordinary file commands replace the old specialized rule read/write tools. Platform HTTP operations and authoritative lifecycle transitions remain SDK responsibilities.

| Agent-visible path | Purpose |
| --- | --- |
| `/rules/**/*.md` | Searchable, editable working rule snapshot |
| `/context.md` | Editable active notes for the session |
| `/inbox/notice.json` | Read-only assigned failure notice |
| `/inbox/evidence.txt` | Read-only diagnostic evidence |
| `/decisions/status.json` | Read-only proposal and validation summaries |

These are virtual paths, not directories at the root of the developer's machine. The supplied interpreter has no host mounts, inherited credentials, network access, or arbitrary external programs. It cannot write authoritative accepted revisions. Other privileged tools supplied by an application are outside that isolation boundary.

Guidance retrieval is agent-driven: the agent decides what to search and read, including ordinary `grep`, `cat`, and similar commands. Reflect provides memory instructions and refreshes a bounded active-memory block at supported checkpoints. It does not automatically insert the entire rule corpus or select rules through a static host retrieval policy.

`context.md` is unvalidated working memory, distinct from shared accepted guidance. Its reuse is scoped by session and accepted revision; notes associated with candidate rule edits are not carried into an ordinary fresh view. Validation starts with fresh local memory. Reflect does not rewrite or compress the rest of a framework's conversation. Filesystem and tool-output limits are not guarantees about the total model context window.

Rules are Markdown with a title, applicability text, and actionable guidance. The agent can add, revise, merge, move, shorten, or remove them. All shared rule changes, including cleanup, go through proposal and validation. Exact duplicate detection exists; semantic contradictions and relevance are not solved automatically by a general-purpose memory index.

The durable workspace contains accepted revisions, working execution snapshots, proposals and decisions, evidence, lifecycle events, and coordination state. Its default location is below `.pandaprobe/reflect/`, partitioned by platform identity. The language implementations have equivalent behavior but do not support simultaneous mixed-language writers to one workspace. Active-rule limits do not automatically prune historical revisions or evidence.

## Acceptance and improvement claims

Ordinary fresh executions start from accepted rules. Candidate text is visible in its authoring execution and explicitly assigned trials. Candidate exposure and acceptance are different concepts; it would be inaccurate to say that every candidate is hidden until acceptance.

Validation compares fresh **control** executions using the baseline with **candidate** executions using the proposed change. The application supplies reproducible cases, fresh business state, and an independent verifier. A trace alone cannot reproduce an arbitrary environment. The proposing model cannot accept its own proposal through the shell.

Default validation requires at least three paired cases, including a protected successful control, complete outcome evidence, and regression checks. Improved outcomes can support acceptance. A smaller rule corpus can also be accepted as maintenance when its non-inferiority checks pass; this is not an observed-improvement claim. Exact thresholds and decision conditions are documented in the validation and configuration pages and implemented in each SDK's validator.

Accepted guidance is evidence under the tested conditions, not a guarantee of compliance or future success. Missing evaluation scores, an empty response, or a completed reflection call are not success evidence.

### The delivery-checker decision

An early core delivery checker tried to prove that rule text reached the model, including complete-file coverage and numbered `grep` handling. Live runs showed that useful excerpts could reach the agent and lead to correct behavior while this conservative checker still failed the demonstration.

The core checker was removed deliberately. Production Reflect has no exact-text or whole-file delivery gate, no core delivery-receipt API, and no delivery condition on rule acceptance. The live examples retain their own observation audit to demonstrate retrieval before the business action. Those audits are test instrumentation, not production policy. Guidance being available, text being observed in model input, and independently verified task success remain separate facts.

### Operational boundaries

- Reflect is explicitly enabled. Ordinary tracing imports and activation do not start evaluation polling, create Reflect workspaces, or invoke reflection models.
- Existing tracing integrations remain responsible for tracing. `TraceCapture` records trace references within a scope; it is not another exporter or a second set of framework patches.
- Task, reflection, and validation attribution are distinct, preventing the loop from reacting recursively to its own internal activity.
- Native platform clients reuse the SDK's resolved endpoint/authentication/project configuration and own a separate HTTP lifecycle. Reflect has no CLI authentication or subprocess dependency.
- Trace export acceptance, persistence, evaluation acceptance, and usable scores are different states. Known run IDs are polled rather than recreated.
- The current evaluation-creation API has no idempotency-key contract. An uncertain create response is recorded as `creation_unknown`, without automatically issuing a potentially duplicate billable run.
- The former default daily cap of 100 evaluation creations was removed. The count is uncapped by default, with an explicit optional cap and other sampling/concurrency controls. This is separate from service quotas and model-provider limits.
- Monitoring and scheduled evaluation are platform capabilities, not prerequisites for the default reflection loop.

## Judge-prompt treatment

The latest backend prompt changes use the explicit term **“Reflect rule and memory operations.”** Reflect is optional; such operations may be absent from a trace. Their presence, absence, frequency, and cost are neutral for the task judges. Actual task actions and mistakes remain assessable, even when attempted through a Reflect-named tool.

Step efficiency assesses task-directed steps. Argument correctness can return `neutral` for Reflect rule and memory operations; neutral verdicts remain in metadata but are excluded from the score denominator. The existing nothing-to-evaluate convention returns 1.0 when no task arguments remain, with an explanatory reason; that is not proof of task completion.

This scoring policy does not remove actual token usage, latency, or monetary cost from tracing and operational reporting. The earlier wording that penalized Reflect administration frequency/cost was intentionally replaced with the shorter neutral policy.

The initial successful live examples ran against the older production judge prompts, which already contained Harness-neutrality notes. They demonstrated selected task-completion and independently verified refund outcomes, not that every judge metric was calibrated or that the revised prompts were deployed. The recent prompt/scoring changes passed 64 evaluation unit tests; no new live judge comparison was performed in that refinement.

## Current documentation structure

The site is Mintlify with the **Aspen** theme and Lucide icons. Its top navigation is **Overview → Trace → Evaluate → Reflect → Reference → Changelog**.

| Tab | Current organization |
| --- | --- |
| **Overview** | One `/overview` landing page using the former welcome content; no navigation sidebar. The separate Architecture page was removed. |
| **Trace** | Get Started; **Tracing setup** containing **Integrations → LLM Providers / Agent Frameworks**, Manual Instrumentation, Sessions, Users, and Configuration. The Integrations menu uses `plug`. |
| **Evaluate** | Get Started; **Evaluation types → Trace Evaluation / Session Evaluation**; Set Up Evaluation. Programmatic Scoring is under Trace Evaluation. |
| **Reflect** | Get Started: Quickstart and How Reflect works. **Using Reflect**: Rules and memory, Validate guidance, Integrations, and Configuration. |
| **Reference** | Overview; SDKs with Python and TypeScript references; HTTP API; Tools containing CLI and Skill. |
| **Changelog** | Python SDK, TypeScript SDK, core service, and CLI. Reflect release notes belong to the SDK changelogs. |

The Reflect Integrations menu contains an overview, eight framework pages across the two languages, and Custom loops. Its Configuration menu contains **Settings** and **Operations**. The longer “Operations and troubleshooting” label was shortened. Reflect has sixteen pages and no separate Runnable examples page or dedicated changelog.

“Agent Evaluation” was renamed to **Session Evaluation** in evaluation documentation and page paths. Existing metric identifiers such as `agent_reliability` and `agent_consistency` retain their actual API names. Tracing's scoped instrumentation page is titled **Scoped tracing** and covers both Python context managers and TypeScript callback scopes. **Client API** is the shortened sidebar label for Low-Level Client API.

The Overview tab has no icon and uses `mode: "custom"` for a genuinely sidebar-free page. `mode: "center"` still left a sidebar in the tested Aspen preview. The custom layout includes explicit typography and responsive card grids; switching to another tab restores its normal sidebar. The Reflect top-tab icon is **`undo-dot`**. Reference and Changelog sidebar entries have no icons; this does not remove icons from every content card or other tab.

CLI and Skill are under Reference → Tools, with their source files in `docs/reference/tools/` and URLs at `/reference/tools/cli` and `/reference/tools/agent-skill`. The former Introduction and Overview tool URLs redirect directly to those destinations. “Skill” remains the surface label; the filename is still `agent-skill.mdx`. The old Introduction/Welcome routes redirect directly to `/overview`. Other moved published pages, including scoring and Session Evaluation, have redirects recorded in `docs.json`. The removed Architecture page has no replacement redirect.

All nineteen legacy Harness pages and its dedicated changelog were removed. There is no legacy migration guide or Harness URL redirection layer. Old research provenance remains outside the public product documentation; old Harness releases were not relabeled as Reflect releases.

## Documentation presentation decisions

The intended experience is clean, lean, and easy to scan, with short navigation labels and a quick path from installation to a working agent. This is an editorial goal, not a measured integration-time guarantee.

- The Reflect quickstart uses a four-step timeline: **install → set credentials → run an agent with Reflect → read the result**.
- Installation examples cover **pip, uv, npm, yarn, and pnpm**. PandaProbe installation commands omit minimum-version suffixes such as `>=0.6.0`; release history belongs in the changelog. Native dependency requirements are a separate concern.
- Shared documentation uses Python/TypeScript code tabs with actual language-specific APIs. Unsupported framework/language combinations are explicit.
- Framework pages provide background, installation, credentials, integration code, and relevant lifecycle differences rather than an unexplained snippet catalogue.
- Quickstarts are self-contained and do not ask readers to create arbitrarily named `support.py` or `support.ts` files. Partial validation examples identify application-owned helpers as such.
- The concepts introduction explains the failure-evidence-to-guidance loop directly. The workflow diagram is vertical because the earlier horizontal layout was cramped.
- The main narrative is useful reflection and tested guidance, not an automatic-repair promise or an aside about model weights.
- Repository example links are supplementary; the main documentation is usable without visiting the SDK source tree. Optional complete examples are linked from validation.

## Centralized API and SDK references

The former API Reference tab is now **Reference**. Its HTTP API remains generated from [OpenAPI](docs/reference/api/openapi.json), with the introduction alongside it. The schema was relocated without changing its endpoint contracts; Mintlify's generated endpoint URLs remain under `/api-reference/...` even though the source files live in `docs/reference/api/`.

The Python and TypeScript references cover tracing, clients/configuration, data contracts, providers, framework integrations, native platform resources, and Reflect. They contain fifteen pages per language plus a shared landing page. Signatures, exports, and fields are extracted from the SDK source, while explanatory notes and examples are reviewed content.

The maintenance tooling lives in [docs/_tools/sdk-reference](docs/_tools/sdk-reference), grouped with the documentation. Python AST and the TypeScript compiler supply declarations without importing optional agent/model runtimes. Authored notes, field descriptions, and example fragments live with the generator. [docs/.mintignore](docs/.mintignore) excludes this tooling from the published site. The former root `scripts/` directory was removed after the move.

The [reference manifest](docs/reference/sdk-reference-manifest.json) records source revision, exports, symbols, methods, fields, and page associations. The last verified snapshot is SDK commit `92d8c37fba00e87ac6f0104cd293990aa5d5e621`, with 115 Python import entries and 110 TypeScript export entries. These counts describe that snapshot rather than a permanent package-size guarantee. The [maintainer README](docs/README.md) records generation and validation commands.

## Evidence and document state

The Python and TypeScript technical reports contain the detailed implementation history, validation results, native-framework issues, and saved live-run evidence. The Python report describes the 0.6.0 release. The TypeScript report begins with an earlier pre-release snapshot and includes a later PR-review revision; its opening version/publication statements predate the subsequently released 0.5.0 package.

The live failure scenario uses a fictional refund service with a deliberately stale runbook: an initial refund includes nonrefundable shipping, a proposed rule changes the behavior, paired control/candidate replays check the actual ledger, and a fresh execution retrieves accepted guidance. These examples separate proposal quality, retrieval observation, business success, and operational failures. Successful selected runs do not establish a general benchmark win or prove all frameworks/providers behave identically.

Documentation verification already performed includes Mintlify build/link checks, source-generation consistency, Python snippet parsing, TypeScript checking, and representative offline native-framework examples with mocked model/platform calls. The Overview layout was additionally checked in a real headless browser at desktop/mobile sizes and in light/dark themes. The latest tooling relocation passed the generator check and Mintlify validation, with generated reference files unchanged. These documentation checks are distinct from live model evaluation and release CI.

At this snapshot the core repository is on `feat/python-reflect-judge-guidance`. The judge refinements are in commits `20b8bd2` and `ab4de15`; the documentation refactor remains local working-tree changes. Production deployment of those judge refinements was not established by this documentation work. The SDK checkout represents the released implementations and was not changed during the documentation refactor.

## Source locations

Paths below are relative to the core repository root. The sibling checkouts used in this work are `../pandaprobe-sdk` and `../pandaprobe-harness`.

### Product behavior and SDK implementation

| Subject | Python | TypeScript |
| --- | --- | --- |
| Detailed implementation history | [Technical report](../pandaprobe-sdk/python-reflect-technical-report.md) | [Technical report](../pandaprobe-sdk/typescript-reflect-technical-report.md) |
| Package/runtime dependencies | [pyproject.toml](../pandaprobe-sdk/libraries/python/pyproject.toml) | [package.json](../pandaprobe-sdk/libraries/typescript/package.json) |
| Public Reflect surface and lifecycle | [Reflect package](../pandaprobe-sdk/libraries/python/src/pandaprobe/reflect), [runtime](../pandaprobe-sdk/libraries/python/src/pandaprobe/reflect/runtime.py) | [Reflect package](../pandaprobe-sdk/libraries/typescript/src/reflect), [runtime](../pandaprobe-sdk/libraries/typescript/src/reflect/runtime.ts) |
| Defaults and outcome types | [config.py](../pandaprobe-sdk/libraries/python/src/pandaprobe/reflect/config.py), [models.py](../pandaprobe-sdk/libraries/python/src/pandaprobe/reflect/models.py) | [config.ts](../pandaprobe-sdk/libraries/typescript/src/reflect/config.ts), [models.ts](../pandaprobe-sdk/libraries/typescript/src/reflect/models.ts) |
| Agent integration and native differences | [integrations.py](../pandaprobe-sdk/libraries/python/src/pandaprobe/reflect/integrations.py), [adapters](../pandaprobe-sdk/libraries/python/src/pandaprobe/reflect/adapters) | [integrations.ts](../pandaprobe-sdk/libraries/typescript/src/reflect/integrations.ts), [adapters](../pandaprobe-sdk/libraries/typescript/src/reflect/adapters) |
| Shell and durable rules | [shell.py](../pandaprobe-sdk/libraries/python/src/pandaprobe/reflect/shell.py), [workspace.py](../pandaprobe-sdk/libraries/python/src/pandaprobe/reflect/workspace.py) | [shell.ts](../pandaprobe-sdk/libraries/typescript/src/reflect/shell.ts), [workspace.ts](../pandaprobe-sdk/libraries/typescript/src/reflect/workspace.ts) |
| Independent acceptance | [validation.py](../pandaprobe-sdk/libraries/python/src/pandaprobe/reflect/validation.py) | [validation.ts](../pandaprobe-sdk/libraries/typescript/src/reflect/validation.ts) |
| Evaluation and detection | [evaluation.py](../pandaprobe-sdk/libraries/python/src/pandaprobe/reflect/evaluation.py), [signals.py](../pandaprobe-sdk/libraries/python/src/pandaprobe/reflect/signals.py) | [evaluation.ts](../pandaprobe-sdk/libraries/typescript/src/reflect/evaluation.ts), [signals.ts](../pandaprobe-sdk/libraries/typescript/src/reflect/signals.ts) |
| Native platform HTTP resources | [api package](../pandaprobe-sdk/libraries/python/src/pandaprobe/api) | [api package](../pandaprobe-sdk/libraries/typescript/src/api) |
| Trace capture | [capture.py](../pandaprobe-sdk/libraries/python/src/pandaprobe/tracing/capture.py) | [capture.ts](../pandaprobe-sdk/libraries/typescript/src/tracing/capture.ts) |
| Examples and live scenarios | [Framework examples](../pandaprobe-sdk/libraries/python/examples), [Reflect examples](../pandaprobe-sdk/libraries/python/examples/reflect) | [Framework examples](../pandaprobe-sdk/libraries/typescript/examples), [Reflect examples](../pandaprobe-sdk/libraries/typescript/examples/reflect) |
| Behavioral tests | [Tests](../pandaprobe-sdk/libraries/python/tests) | [Reflect tests](../pandaprobe-sdk/libraries/typescript/test/reflect), [native tests](../pandaprobe-sdk/libraries/typescript/test/native) |

Example-only delivery auditing lives in [Python delivery.py](../pandaprobe-sdk/libraries/python/examples/reflect/_support/delivery.py) and [TypeScript delivery.ts](../pandaprobe-sdk/libraries/typescript/examples/reflect/_support/delivery.ts). The original [Harness repository](../pandaprobe-harness) and its [paper directory](../pandaprobe-harness/paper) contain historical research, not current SDK contracts.

### Core service and documentation

| Subject | Location |
| --- | --- |
| Navigation, labels, redirects, theme | [docs/docs.json](docs/docs.json) |
| Sidebar-free product landing page | [docs/overview.mdx](docs/overview.mdx) |
| Reflect narrative and integration guides | [docs/reflect](docs/reflect) |
| SDK and HTTP reference pages | [docs/reference](docs/reference) |
| Reference maintenance and generation | [Maintainer README](docs/README.md), [tooling](docs/_tools/sdk-reference), [publishing exclusions](docs/.mintignore) |
| Release context | [Python changelog](docs/changelog/python-sdk.mdx), [TypeScript changelog](docs/changelog/typescript-sdk.mdx) |
| Trace and evaluation endpoints | [traces.py](backend/app/api/v1/routes/traces.py), [evaluations.py](backend/app/api/v1/routes/evaluations.py) |
| Authentication/project resolution | [dependencies.py](backend/app/api/dependencies.py) |
| Evaluation orchestration | [eval_service.py](backend/app/services/eval_service.py) |
| Metric definitions and judge templates | [metrics](backend/app/core/evals/metrics), [shared Reflect guidance](backend/app/core/evals/metrics/utils.py) |
| Neutral verdict handling | [Argument correctness](backend/app/core/evals/metrics/trace/argument_correctness) |
| Judge regression coverage | [test_reflect_judge_prompts.py](backend/tests/unit/test_reflect_judge_prompts.py) |

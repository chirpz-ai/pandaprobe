"""Reviewed behavioral context accompanying source-generated SDK contracts."""

PAGES = {
    "client": ("Client", "Initialize tracing, submit traces and scores, and manage export lifecycle"),
    "configuration": ("Configuration", "Tracing credentials, environment settings, and resolved client options"),
    "tracing": ("Tracing and context", "Decorators, trace and span contexts, session propagation, and trace capture"),
    "data": ("Trace data", "Trace, span, score, and message contracts"),
    "wrappers": ("Provider wrappers", "Instrument provider clients while preserving their native calls and results"),
    "integrations": ("Framework integrations", "Callbacks, adapters, and native agent tracing hooks"),
    "platform-client": ("Platform client", "Read persisted traces and create or poll evaluation runs"),
    "platform-models": ("Platform models", "Typed trace evidence, evaluation runs, metrics, and scores"),
    "platform-errors": (
        "Platform errors",
        "Distinguish failed requests, deadlines, insufficient evidence, and uncertain creation",
    ),
    "reflect-runtime": (
        "Reflect runtime",
        "Run the agent, evaluate evidence, continue reflection, and inspect outcomes",
    ),
    "reflect-config": ("Reflect configuration", "Workspace, evaluation, shell, context, and validation options"),
    "reflect-execution": (
        "Execution and invocation",
        "Execution boundaries, attribution, active memory, and host callbacks",
    ),
    "reflect-validation": (
        "Replay and validation",
        "Independent outcomes, paired replay, controlled trials, and acceptance",
    ),
    "reflect-models": ("Rules and results", "Persistent rules, proposals, notices, reports, and validation records"),
}

INTRO = {
    "client": """The tracing client owns configuration and a background export queue. Use an explicit client when an application needs separate identities; use the module-level helpers for the global client. Initialization does not activate Reflect.

Client construction resolves credentials from arguments and environment variables. Missing API key or project name raises when tracing is enabled. The global getter attempts environment initialization once and returns no client if it cannot initialize. Reinitializing the global client shuts down its predecessor.

`score` submits a programmatic score; it does not start a platform evaluation. Scores use a string value, including numeric values such as `"0.95"`. Export completion is separate from platform persistence and evaluation completion.

See [tracing quickstart](/tracing/get-started/quickstart) for provider/framework setup.""",
    "configuration": """Explicit constructor options override `PANDAPROBE_*` environment variables. The resolved configuration is immutable. The tracing client requires an API key and project name when enabled; platform API access requires both even if tracing is disabled.

| Environment variable | Default |
| --- | --- |
| `PANDAPROBE_API_KEY` | Unset |
| `PANDAPROBE_PROJECT_NAME` | Unset |
| `PANDAPROBE_ENDPOINT` | `https://api.pandaprobe.com` |
| `PANDAPROBE_ENVIRONMENT` | Unset |
| `PANDAPROBE_RELEASE` | Unset |
| `PANDAPROBE_ENABLED` | `true` |
| `PANDAPROBE_BATCH_SIZE` | `10` |
| `PANDAPROBE_FLUSH_INTERVAL` | `5` seconds |
| `PANDAPROBE_MAX_QUEUE_SIZE` | `1000` |
| `PANDAPROBE_DEBUG` | `false` |

Boolean environment settings recognize `true`, `1`, and `yes` as true. Provider credentials belong to the provider SDK. Reflect reuses the same PandaProbe identity; its policy settings are documented separately.""",
    "tracing": """A trace represents one application invocation; spans record work inside it. Use a trace's span factory or decorators so parentage and context are established automatically. Exceptions from traced application code propagate after recording an error.

Trace input contains the current turn's user message; trace output contains the final assistant message. LLM spans can contain the full model message history. Session and user scopes propagate attribution; they do not store an agent conversation.

Trace capture observes IDs submitted by existing instrumentation. It does not create traces or wait for export/persistence. Consume streams inside the capture/execution boundary. A capture is single-use; late descendant work retains attribution but is no longer added to the closed capture's ID list.""",
    "data": """These are trace-export records, not the platform read models. Construct them for low-level submission through the tracing client, or let contexts and framework integrations construct them.

The wire representation uses snake_case, string enum values, and ISO-8601 timestamps. Serialization omits selected null/empty fields as defined by each record's serializer. Trace and LLM-span input/output use `{"messages": [{"role": "user", "content": "..."}]}`; other span kinds can carry domain-specific values.

Token usage records prompt/completion/total tokens and may include provider-specific numeric usage. Cost is a dictionary of monetary amounts; the SDK does not calculate missing provider prices.""",
    "wrappers": """Wrap the provider client before using it. Calls retain their native arguments, results, exceptions, and streaming behavior. Instrumented calls attach to the active trace or create a standalone trace when needed. Finish or close streams so their trace can be finalized.

Provider packages are optional. Install the provider you use alongside `pandaprobe`; the wrapper does not replace the provider's own API reference. These functions instrument model calls, while the [framework integrations](/tracing/integrations/overview) also capture agent/tool structure.""",
    "integrations": """These APIs enable tracing. They do not enable reflection by themselves. Use the same explicit client for tracing and Reflect when combining them.

LangChain, LangGraph, and DeepAgents use callback handlers passed to native invocation configuration. Their inherited callback methods are framework hooks; applications normally construct a handler once and let the framework call it. The callback contracts below include those inherited SDK methods.

Other integrations use the framework's adapter, processor, query wrapper, or agent wrapper. Register instrumentation once at application startup. See [Reflect integrations](/reflect/frameworks) for memory tooling and reflection continuation.""",
    "platform-client": """This asynchronous HTTP client reads persisted evidence and starts or polls trace evaluations independently of trace export. It reuses an existing tracing client's resolved endpoint, API key, and project, with a separate lifecycle. Close it separately when you supply it to Reflect.

The SDK currently exposes trace reads and trace evaluation resources. The [HTTP API](/reference/api/introduction) also documents operations such as sessions and monitors that are not typed SDK resources here.

All timeouts and polling intervals are **seconds**. Safe GETs have bounded retries; evaluation creation is sent once because the server has no idempotency-key contract. Poll the returned run ID. An uncertain create outcome must not be automatically retried.

`wait_visible` / `waitVisible` waits for a terminal persisted trace, including an error trace. Evaluation `wait` requires usable scores for every requested trace/metric pair; terminal status alone is insufficient. Missing, duplicate, nonnumeric, or failed evidence does not become a passing result.""",
    "platform-models": """Platform read models preserve the server's snake_case field names in both SDKs. They are separate from trace-export records. Status values and required fields below come from the SDK contracts.

An evaluation result contains a completed run and usable requested scores. It does not by itself demonstrate behavioral improvement. A numeric score is usable only when its status is `SUCCESS`, its data type is `NUMERIC`, and its value parses to a finite number.""",
    "platform-errors": """Catch errors at the operation boundary. Authentication errors, missing resources, rate limits, read transport failures, deadlines, and incomplete evaluation evidence have separate types.

`CreationOutcomeUnknown` means the server may already have created a billable evaluation. Keep that outcome distinct from a known failed request; do not create another run automatically. Cancellation is separate from these operational errors.

| Error | Meaning |
| --- | --- |
| `PlatformError` | Base platform error |
| `ApiError` | Non-success HTTP response; includes status and request ID when available |
| `AuthenticationError` | HTTP 401 or 403 |
| `NotFoundError` | HTTP 404 |
| `RateLimitError` | HTTP 429 after applicable read retries |
| `TransportError` | A read could not complete through the transport |
| `ApiDeadlineExceeded` | Operation or polling deadline exceeded |
| `InvalidResponseError` | Invalid JSON, response shape, or mismatched response identity |
| `CreationOutcomeUnknown` | A create may have reached the server; response cannot establish its outcome |
| `EvaluationFailed` | Evaluation ended `FAILED` or `CANCELLED` |
| `InsufficientEvidence` | Required trace/metric pairs are missing, duplicated, or unusable |
""",
    "reflect-runtime": """Reflect coordinates **Detect → Notify → Reflect → Validate** around an explicit agent invocation. The same task agent receives failure evidence and proposes filesystem changes; independent validation owns acceptance.

`run` returns the original task result after evaluation and any triggered reflection. It does not replace the task answer with the reflection answer. Task exceptions propagate. Validation settles separately so replay can acquire resources released by the task.

Native agent construction attaches the supplied `reflect_bash` tool and memory instructions. A generic asynchronous callback receives an `Invocation` and must pass its instructions/tool to the model and enforce phase permissions itself. See the [quickstart](/reflect/quickstart), [native integrations](/reflect/frameworks), and [custom loop guide](/reflect/custom-loops).

Use unique execution IDs and related-work session IDs. Importing Reflect alone starts no work; constructing it opens its configured persistent workspace. Close Reflect and then the tracing client. An externally supplied platform client remains caller-owned.""",
    "reflect-config": """Start with defaults. These options govern Reflect policy, not the task model/provider. Durations are seconds and sizes count UTF-8 bytes. `PANDAPROBE_REFLECT_WORKSPACE` supplies the default workspace; explicit configuration takes precedence.

There is **no default daily evaluation-run cap**. An explicit positive count limits workspace-wide creation attempts per UTC day, including diagnostic/failed/uncertain creates. Polling known runs does not consume another creation attempt.

Scores and probability settings must be finite in `[0, 1]`; timeouts must be finite and positive; capacities/counts must be positive integers. Cooldown can be zero. Thresholds must contain named metrics. Size limits govern the supplied shell and active files, not the framework's entire history or model bill.

See [Reflect settings](/reflect/configuration) for how these controls interact. Both languages persist records using snake_case; configuration parameter naming follows the language.""",
    "reflect-execution": """An execution pins rule state, working files, trace attribution, and a unique identity. Obtain it from the runtime's execution or trial factory. An execution is single-use; do not manually switch its role to bypass validation assignment.

An `Invocation` is the generic host callback input. Its current instructions include the filesystem contract and active memory. During reflection, the callback also receives feedback and the prior result. Deliver instructions to the actual model, and expose only Reflect filesystem administration during reflection.

Ending a task execution seals changes and schedules evaluation; it does not itself invoke a continuation. Use the runtime's explicit continuation for delayed feedback. Accepted rules, trial candidates, active session notes, and native framework conversation history are separate state.""",
    "reflect-validation": """Supply reproducible cases, a fresh business environment for every arm, and an independent verifier. The agent's statement that it succeeded is not an outcome measurement.

Each case compares control rules with candidate rules under fresh identities and active memory. Defaults require three distinct pairs including a protected successful control, complete normalized metric evidence, no success regression, no per-case metric decrease beyond `0.02`, and mean non-protected improvement of at least `0.05`. A strict reduction in guidance bytes can qualify as maintenance under the same non-regression checks.

Return scores for every configured threshold metric and an explicit boolean success. Incomplete evidence stays pending. Acceptance publishes a new immutable revision; it is evidence under tested conditions, not a permanent guarantee.

Use `Reflect.validate` for replay. The `validator` property exposes lower-level replay, assessment, and controlled-trial recording for host code. Do not expose acceptance methods to the proposing agent. See [Validate guidance](/reflect/validation) for the integration recipe.""",
    "reflect-models": """These records separate proposal generation, evaluation, acceptance, and independently verified outcomes. Persisted names remain snake_case in both languages.

Rules are relative Markdown files. Each needs a title, an `Applies to: ...` line, and behavioral guidance. A proposal records a change set against a specific accepted base revision; a null change deletes a file. Ordinary fresh executions receive accepted rules, while candidates are visible during authoring and explicit trials.

| Layer | Status values |
| --- | --- |
| Evaluation | `evaluated`, `skipped`, `pending`, `insufficient`, `failed`, `creation_unknown`, `cancelled` |
| Proposal generation | `proposed`, `duplicate`, `no_proposal`, `invalid`, `conflict`, `timed_out`, `failed`, `cancelled` |
| Proposal lifecycle | `candidate`, `pending`, `accepted`, `rejected` |

Task completion in an execution report describes runtime execution; use an independent verifier for business success. A reported rationale is agent-authored evidence, not proof of improvement.""",
}

LANGUAGE_NOTES = {
    (
        "python",
        "client",
    ): "`flush()` and `shutdown()` block; call them outside latency-sensitive async work or offload them when necessary. `Client` does not install itself as the global client; `init()` does.",
    (
        "typescript",
        "client",
    ): "Await `flush()` and `shutdown()`. `Client` does not install itself as the global client; `init()` does. Global helpers return promises where the underlying operation is asynchronous.",
    (
        "python",
        "tracing",
    ): "Trace/span contexts support both `with` and `async with`. Function decorators support synchronous and asynchronous functions; `span` without an active trace simply executes the original function. `start_trace` raises if no global client is available. For capture, use `with client.capture_traces(...) as capture`.",
    (
        "typescript",
        "tracing",
    ): "Use `withTrace`/`withSpan` for callback functions or `trace`/`span` for native class-method decorators (legacy and Stage 3 forms). A `TraceContext` can own a callback with `run`, or be explicitly entered and ended. Always finish explicit contexts. Session/user callback scopes use AsyncLocalStorage. `TraceCapture` is a type-only root export: obtain it from `client.captureTraces(...)` and call `run(...)`.",
    (
        "python",
        "data",
    ): "Export records are Pydantic models. Required fields and defaults are shown below; `to_api_dict()` performs wire serialization. Standard Pydantic construction and serialization methods remain available. Validation helpers report malformed message structure; they do not validate business correctness.",
    (
        "typescript",
        "data",
    ): "Construct `SpanData`, `TraceData`, and `ScoreData` with their init objects; `toApiDict()` performs wire serialization. The init interfaces shown below describe accepted objects but are not independently exported at the package root.",
    (
        "python",
        "wrappers",
    ): "Provider helpers are available from `pandaprobe.wrappers` and their provider submodules. `wrap_litellm()` is the exception to instance wrapping: it instruments module-level completion functions. Bedrock async support depends on the supplied native client.",
    (
        "typescript",
        "wrappers",
    ): "Import each wrapper from its documented provider subpath. There is no exported `pandaprobe/wrappers` aggregate or TypeScript LiteLLM wrapper. Bedrock instrumentation wraps the native client’s `send` method.",
    (
        "python",
        "integrations",
    ): "Google ADK, Claude Agent SDK, and CrewAI adapters expose synchronous `instrument()` registration. OpenAI Agents uses its native tracing processor hooks. Framework packages remain optional; constructing/importing a particular integration may require its optional dependency. Constructor `**kwargs` on LangChain-family handlers accepts the shared adapter identity options: `client`, `session_id`, `user_id`, `tags`, and `metadata`.",
    (
        "typescript",
        "integrations",
    ): "Await OpenAI Agents `instrument()` or use its processor factory with the native SDK. Claude integration wraps the query function because ESM modules cannot be patched like Python modules. Vercel model middleware instruments LLM calls; `wrapVercelAgent` adds the agent/step/tool hierarchy. Google ADK and CrewAI are not TypeScript exports.",
    (
        "python",
        "platform-models",
    ): 'Platform models use Pydantic. Read models preserve additive server fields (`extra="allow"`). `Score.numeric_value` is a property. `EvaluationRequest` is available from `pandaprobe.api.models`; ordinary callers use `api.evaluations.create(...)`.',
    (
        "typescript",
        "platform-models",
    ): "These are TypeScript interfaces, not model constructors. Resource methods validate response fields before returning typed objects. Use the exported `numericValue(score)` function for usable numeric score conversion.",
    (
        "python",
        "reflect-runtime",
    ): "`agent(...)` and `tool(...)` construct synchronously; `run(...)`, `bash(...)`, and settlement operations are awaited. `submit_traces(...)` and `validate(...)` return scheduled asyncio Tasks. Use `async with Reflect(client)` or `await reflect.aclose()`.",
    (
        "typescript",
        "reflect-runtime",
    ): "Import `Reflect` from `pandaprobe/reflect`; alias it to `ReflectRuntime` when also using JavaScript’s built-in Reflect. Await `agent(...)`, `tool(...)`, `run(...)`, and `close()`. Supported native framework identifiers and agent options are listed below.",
    (
        "python",
        "reflect-execution",
    ): "The async execution context seals and schedules on exit. `instructions()` rebuilds one replaceable instruction block. Host-owned `activate()` scopes attribution; it is not a model-facing permission API.",
    (
        "typescript",
        "reflect-execution",
    ): "Use `await reflect.execution(options, callback)` so cleanup is paired with the callback. The invocation carries an AbortSignal; propagate it through your host loop. Cancellation is cooperative. The underlying Execution lifecycle methods support advanced hosts, but ordinary callers should use runtime factories.",
    (
        "python",
        "reflect-models",
    ): "Records are frozen Pydantic models with unknown fields rejected. `model_dump()` / `model_dump_json()` serialize them; `model_validate()` reconstructs them. Validators shown below enforce record shape, not behavioral correctness.",
    (
        "typescript",
        "reflect-models",
    ): "`Rule` is a runtime class; most result records are interfaces returned by Reflect, not constructors. `RuleProposal.changes` maps paths to rule records or null deletions. Internal record builders are not package exports.",
}

# Notes supplement terse or absent source docstrings, without changing signatures.
METHOD_NOTES = {
    "Reflect.tool": "Returns the supplied tool in a generic or native framework format. The generic tool accepts a command string and must run inside an active Reflect boundary.",
    "Reflect.agent": "Builds a supported native agent with Reflect tools and memory integration. Pass the framework’s factory/constructor and its native options; do not also add reflect_bash manually.",
    "Reflect.submit_traces": "Schedules evaluation for completed trace references; identities must belong to the same project. Reusing a trace under a different execution ID is rejected.",
    "Reflect.submitTraces": "Schedules evaluation for completed trace references; identities must belong to the same project. Reusing a trace under a different execution ID is rejected.",
    "Reflect.report": "Returns the execution’s task, evaluation, reflection, and proposal outcomes. Does not infer business success from task completion.",
    "Reflect.proposals": "Returns persisted proposals, including their lifecycle state and decision evidence.",
    "Reflect.settle_evaluation": "Waits for evaluation evidence for this execution. A caller wait deadline can leave the underlying run pending.",
    "Reflect.settleEvaluation": "Waits for evaluation evidence for this execution. A caller wait deadline can leave the underlying run pending.",
    "Reflect.settle_reflection": "Waits for an already scheduled reflection checkpoint. A caller wait timeout is distinct from the checkpoint’s execution deadline.",
    "Reflect.settleReflection": "Waits for an already scheduled reflection checkpoint. A caller wait timeout is distinct from the checkpoint’s execution deadline.",
    "Reflect.resume_evaluations": "Resumes persisted pending evaluation work after restart; known evaluation IDs are polled instead of recreated.",
    "Reflect.resumeEvaluations": "Resumes persisted pending evaluation work after restart; known evaluation IDs are polled instead of recreated.",
    "Reflect.continue_reflection": "Uses the supplied host continuation when evaluation has produced a failure notice. Delayed feedback does not automatically restart an agent.",
    "Reflect.continueReflection": "Uses the supplied host continuation when evaluation has produced a failure notice. Delayed feedback does not automatically restart an agent.",
    "Reflect.aclose": "Cancels owned work, bounds the shutdown wait, and closes an owned platform client. It does not close a caller-supplied platform client or the tracing client.",
    "Reflect.close": "Cancels owned work, bounds the shutdown wait, and closes an owned platform client. It does not close a caller-supplied platform client or the tracing client.",
    "Traces.get": "Fetches one trace with span evidence and verifies that the returned trace ID matches the requested ID.",
    "Traces.list": "Returns a page of trace summaries. Limit must be 1–200 and offset must be nonnegative.",
    "Traces.iterate": "Iterates trace summaries in pages, stopping at the configured maximum or the end of the server result.",
    "Evaluations.metrics": "Returns the supported trace metric metadata from the platform.",
    "Evaluations.create": "Creates one batch trace-evaluation run. Deduplicates trace IDs and metric names and requires nonempty inputs. Creation is never automatically retried.",
    "Evaluations.get": "Fetches one evaluation run and verifies its identity. A RUNNING or PENDING result is not complete evidence.",
    "Evaluations.scores": "Fetches the score records for an evaluation run; use wait to require a complete usable set.",
    "Validator.record_trial": "Records independently measured paired trial evidence and applies the same acceptance policy used for replay.",
    "Validator.recordTrial": "Records independently measured paired trial evidence and applies the same acceptance policy used for replay.",
    "Validator.assess": "Assesses supplied paired rows against acceptance policy. Assessment alone does not publish a revision; use runtime validation or recorded trials.",
    "Client.log_trace": "Queues a prebuilt trace record for export. This is asynchronous ingestion, not confirmation that the trace is persisted.",
    "Client.logTrace": "Queues a prebuilt trace record for export. This is asynchronous ingestion, not confirmation that the trace is persisted.",
    "Client.on_error": "Registers a callback for export transport errors. Errors inside the callback are caught by the SDK.",
    "Client.onError": "Registers a callback for export transport errors. Errors inside the callback are caught by the SDK.",
}


# Shared context setters have the same intent in both languages.
_CONTEXT_METHODS = {
    (
        "set_input",
        "setInput",
    ): "Sets the recorded input. Trace and LLM inputs use the messages schema; other span kinds may use domain values.",
    (
        "set_output",
        "setOutput",
    ): "Sets the recorded output. Trace and LLM outputs use the messages schema; other span kinds may use domain values.",
    (
        "set_metadata",
        "setMetadata",
    ): "Merges metadata into the current record; existing keys with the same name are replaced.",
    ("set_status", "setStatus"): "Sets the trace status using a supported TraceStatus value.",
    ("set_model", "setModel"): "Records the model identifier for this span.",
    ("set_model_parameters", "setModelParameters"): "Records the supplied model invocation parameters.",
    (
        "set_token_usage",
        "setTokenUsage",
    ): "Records supplied token counts and additional numeric usage. This setter does not measure token use itself.",
    (
        "set_cost",
        "setCost",
    ): "Records supplied total cost and any additional named cost components. It does not look up provider prices.",
    (
        "set_completion_start_time",
        "setCompletionStartTime",
    ): "Records the time completion output began, such as the first streamed token.",
    ("set_error", "setError"): "Records an error message and sets the span status to ERROR.",
}
for names, note in _CONTEXT_METHODS.items():
    for cls in ("TraceContext", "SpanContext"):
        for name in names:
            METHOD_NOTES.setdefault(f"{cls}.{name}", note)
for name in ("withCurrent", "assertOpen", "trackExecution", "untrackExecution", "scheduleValidation"):
    METHOD_NOTES[f"Reflect.{name}"] = (
        "Advanced adapter lifecycle hook. Ordinary applications use run/execution and the settlement methods so attribution, scheduling, and cleanup stay paired. Do not expose this hook to the agent."
    )
METHOD_NOTES["Execution.checkpoint"] = (
    "Persists the execution's working snapshot. The runtime normally owns this checkpoint; persistence does not publish accepted guidance."
)
METHOD_NOTES["Execution.seal"] = (
    "Captures rule changes as a proposal against the pinned base revision and checkpoints the execution. It does not accept or publish the proposed rule."
)
LANGUAGE_NOTES[("python", "integrations")] += (
    " LangGraph utility re-exports are included for completeness; prefer the native callback handler for instrumentation."
)

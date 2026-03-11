# Seed Data for Dev Testing

This folder contains realistic trace payloads for manually testing the PandaProbe
API in development. The data covers five distinct scenarios across three sessions,
multiple users, both success and error states, and a variety of span types
(AGENT, LLM, TOOL, CHAIN, RETRIEVER, EMBEDDING).

## What's Inside

| File | Scenario | Session | Status |
|---|---|---|---|
| `01_chatbot_support_turn1.json` | Customer support chatbot — order status inquiry | `session-cs-20260223-jmartinez` | COMPLETED |
| `05_chatbot_support_turn2.json` | Same chatbot — follow-up: resend email + change address | `session-cs-20260223-jmartinez` | COMPLETED |
| `02_rag_pipeline.json` | RAG pipeline — docs Q&A with retrieval, reranking, generation | `session-docsqa-20260223-akim` | COMPLETED |
| `06_add_spans_to_rag.json` | Extra spans added after the fact to trace `02` | *(same trace)* | — |
| `03_code_review_agent.json` | Multi-agent code review (security + perf + style agents) | `session-codereview-pr47` | COMPLETED |
| `04_error_trace.json` | Failed document extraction — 503 from upstream LLM | `session-docextract-batch-20260223` | ERROR |
| `08_docextract_success.json` | Successful document extraction — same session as `04` | `session-docextract-batch-20260223` | COMPLETED |
| `07_simple_summarization.json` | Single-LLM-call article summarization (no session) | *(none)* | COMPLETED |

### Sessions Created

After ingesting all traces, you'll have **4 sessions**:

1. **session-cs-20260223-jmartinez** — 2 traces (customer support conversation)
2. **session-docsqa-20260223-akim** — 1 trace (RAG pipeline)
3. **session-codereview-pr47** — 1 trace (multi-agent code review)
4. **session-docextract-batch-20260223** — 2 traces (1 error + 1 success)

### Data Coverage

- **Span kinds**: AGENT, CHAIN, LLM, TOOL, RETRIEVER, EMBEDDING
- **LLM models**: gpt-4o, gpt-4o-mini, claude-3-5-sonnet, gemini-2.5-flash, text-embedding-3-small, rerank-english-v3.0
- **Environments**: production, staging, development
- **Users**: user-j-martinez-8821, user-alex-kim-3347, user-ci-bot, user-sarah-chen-1104, user-dev-testing
- **Error scenarios**: trace `04` has status ERROR with 3 failed LLM retry spans (503 Overloaded)
- **Token usage & cost**: populated on all LLM spans (null on error spans)
- **completion_start_time**: set on LLM spans to test `time_to_first_token_ms` computation

---

## Prerequisites

1. Dev services must be running:

   ```bash
   make up
   ```

2. You need a valid API key. If you don't have one, create one via the management
   API (requires a Bearer JWT) or directly in the database.

3. You need a project. The API key + `X-Project-Name` header will auto-create one.

---

## Step-by-Step: Ingest via Swagger UI

### Step 1 — Open Swagger

Navigate to **http://localhost:8000/docs** in your browser.

### Step 2 — Authenticate

Click the **Authorize** button (lock icon at the top). Fill in:

- **X-API-Key**: your API key (e.g., `sk_pp_abc123...`)

Click **Authorize**, then **Close**.

### Step 3 — Ingest Traces (POST /traces)

For each of these files **in order**, do:

1. Expand **POST /traces**
2. Click **Try it out**
3. Set the header `X-Project-Name` to your project name (e.g., `my-dev-project`)
4. Copy-paste the JSON content from the file into the request body
5. Click **Execute**
6. Verify you get a `202` response with `trace_id` and `task_id`

**Ingestion order:**

```
01_chatbot_support_turn1.json
02_rag_pipeline.json
03_code_review_agent.json
04_error_trace.json
05_chatbot_support_turn2.json
07_simple_summarization.json
08_docextract_success.json
```

### Step 4 — Add Extra Spans (POST /traces/{trace_id}/spans)

1. Expand **POST /traces/{trace_id}/spans**
2. Click **Try it out**
3. Set `trace_id` to: `a1b2c3d4-0002-4000-8000-000000000001` (the RAG trace)
4. Copy-paste the JSON content from `06_add_spans_to_rag.json` into the request body
5. Click **Execute**
6. Verify you get `201` with the two new `span_ids`

---

## Step-by-Step: Ingest via curl

If you prefer the command line, run from the project root:

```bash
API_KEY="sk_pp_YOUR_KEY_HERE"
PROJECT="my-dev-project"

# Ingest all traces
for f in scripts/seed/0{1,2,3,4,5,7,8}_*.json; do
  echo "Ingesting $f ..."
  curl -s -X POST http://localhost:8000/traces \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -H "X-Project-Name: $PROJECT" \
    -d @"$f" | python3 -m json.tool
  echo ""
done

# Add extra spans to the RAG trace
echo "Adding spans to RAG trace..."
curl -s -X POST http://localhost:8000/traces/a1b2c3d4-0002-4000-8000-000000000001/spans \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" \
  -d @scripts/seed/06_add_spans_to_rag.json | python3 -m json.tool
```

---

## Explore the APIs

After ingesting, try these endpoints to explore the data:

### Traces

| Action | Endpoint |
|---|---|
| List all traces | `GET /traces` |
| Get single trace with spans | `GET /traces/{trace_id}` |
| Filter by status=ERROR | `GET /traces?status=ERROR` |
| Filter by user | `GET /traces?user_id=user-j-martinez-8821` |
| Filter by tags | `GET /traces?tags=rag&tags=knowledge-base` |
| Filter by session | `GET /traces?session_id=session-cs-20260223-jmartinez` |
| Sort by latency | `GET /traces?sort_by=latency&sort_order=desc` |
| Trace analytics (volume) | `GET /traces/analytics?metric=volume&granularity=hour&started_after=2026-02-23T00:00:00Z&started_before=2026-02-24T00:00:00Z` |
| Trace analytics (cost) | `GET /traces/analytics?metric=cost&granularity=hour&started_after=2026-02-23T00:00:00Z&started_before=2026-02-24T00:00:00Z` |
| Trace analytics (models) | `GET /traces/analytics?metric=models&granularity=day&started_after=2026-02-23T00:00:00Z&started_before=2026-02-24T00:00:00Z` |
| Top users | `GET /traces/users?started_after=2026-02-23T00:00:00Z&started_before=2026-02-24T00:00:00Z` |

### Sessions

| Action | Endpoint |
|---|---|
| List all sessions | `GET /sessions` |
| Session detail | `GET /sessions/session-cs-20260223-jmartinez` |
| Filter error sessions | `GET /sessions?has_error=true` |
| Session analytics | `GET /sessions/analytics?granularity=hour&started_after=2026-02-23T00:00:00Z&started_before=2026-02-24T00:00:00Z` |

### Mutations (optional — test write operations)

| Action | Endpoint |
|---|---|
| Update a trace | `PATCH /traces/a1b2c3d4-0007-4000-8000-000000000001` with `{"tags": ["summarization", "tested"]}` |
| Update a span | `PATCH /traces/a1b2c3d4-0001-4000-8000-000000000001/spans/b1000001-0001-4000-8000-000000000005` with `{"metadata": {"reviewed": true}}` |
| Batch add tags | `POST /traces/batch/tags` with `{"trace_ids": ["a1b2c3d4-0001-4000-8000-000000000001", "a1b2c3d4-0005-4000-8000-000000000001"], "add_tags": ["reviewed"]}` |
| Delete a trace | `DELETE /traces/a1b2c3d4-0007-4000-8000-000000000001` |
| Delete a session | `DELETE /sessions/session-codereview-pr47` |

### Things to Verify

After ingesting and exploring, check these behaviors:

1. **Computed fields** — On `GET /traces/{id}`, each span should have `latency_ms` and `time_to_first_token_ms` computed from timestamps
2. **Session aggregation** — `GET /sessions/session-cs-20260223-jmartinez` should show `trace_count: 2`, with `input` from trace 01 (earliest) and `output` from trace 05 (latest)
3. **Error session** — `GET /sessions/session-docextract-batch-20260223` should have `has_error: true` due to trace 04
4. **Span stats on list** — `GET /traces` should show `span_count`, `total_tokens`, and `total_cost` computed per trace
5. **Upsert idempotency** — Re-POST trace 01 and verify the trace is updated (not duplicated)
6. **Added spans** — `GET /traces/a1b2c3d4-0002-4000-8000-000000000001` should show 8 spans (6 original + 2 added)

---

## Test Evaluations

After ingesting the 7 seed traces, you can test the evaluation system. Make sure you have at least one LLM provider configured (e.g. `OPENAI_API_KEY` or `GEMINI_API_KEY` in your `.env`).

### Prerequisite: Check Available Metrics

```bash
API_KEY="sk_pp_YOUR_KEY_HERE"
PROJECT="my-dev-project"

curl -s http://localhost:8000/evaluations/metrics \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" | python3 -m json.tool
```

You should see 6 metrics: `argument_correctness`, `plan_adherence`, `plan_quality`, `step_efficiency`, `task_completion`, `tool_correctness`.

### Get a Run Template (Preview)

Before creating a run, fetch the template for a metric to see its prompt preview and defaults:

```bash
curl -s "http://localhost:8000/evaluations/runs/template?metric=task_completion" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" | python3 -m json.tool
```

### Test 1: Filtered Eval Run (POST /evaluations/runs)

Run `task_completion` on all COMPLETED traces:

```bash
curl -s -X POST http://localhost:8000/evaluations/runs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" \
  -d '{
    "name": "Test: task_completion on completed traces",
    "metrics": ["task_completion"],
    "filters": {
      "status": "COMPLETED"
    }
  }' | python3 -m json.tool
```

This should return `202` with `total_traces: 6` (all COMPLETED traces, excluding the ERROR trace `04`).

Run multiple metrics with a date filter and sampling:

```bash
curl -s -X POST http://localhost:8000/evaluations/runs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" \
  -d '{
    "name": "Test: multi-metric with sampling",
    "metrics": ["task_completion", "step_efficiency"],
    "filters": {
      "date_from": "2026-02-23T00:00:00Z",
      "date_to": "2026-02-24T00:00:00Z"
    },
    "sampling_rate": 0.5
  }' | python3 -m json.tool
```

This evaluates ~50% of matching traces with both metrics.

Run tool-related metrics only on traces with tool spans (the code review and support agents):

```bash
curl -s -X POST http://localhost:8000/evaluations/runs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" \
  -d '{
    "name": "Test: tool metrics on support session",
    "metrics": ["tool_correctness", "argument_correctness"],
    "filters": {
      "session_id": "session-cs-20260223-jmartinez"
    }
  }' | python3 -m json.tool
```

### Test 2: Batch Eval Run (POST /evaluations/runs/batch)

Evaluate specific traces by ID — pick the RAG pipeline and code review agent:

```bash
curl -s -X POST http://localhost:8000/evaluations/runs/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" \
  -d '{
    "name": "Test: batch eval on RAG + code review",
    "trace_ids": [
      "a1b2c3d4-0002-4000-8000-000000000001",
      "a1b2c3d4-0003-4000-8000-000000000001"
    ],
    "metrics": ["task_completion", "step_efficiency", "plan_quality"]
  }' | python3 -m json.tool
```

This evaluates exactly 2 traces with 3 metrics each (6 trace scores total).

Evaluate the error trace to verify it still gets scored (the trace has ERROR status but the LLM judge evaluates what the agent did):

```bash
curl -s -X POST http://localhost:8000/evaluations/runs/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" \
  -d '{
    "name": "Test: eval error trace",
    "trace_ids": [
      "a1b2c3d4-0004-4000-8000-000000000001"
    ],
    "metrics": ["task_completion"]
  }' | python3 -m json.tool
```

### Monitor and Verify Results

Check run progress (replace `RUN_ID` with the `id` from the POST response):

```bash
curl -s http://localhost:8000/evaluations/runs/RUN_ID \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" | python3 -m json.tool
```

Look at `status` (PENDING -> RUNNING -> COMPLETED), `evaluated_count`, and `failed_count`.

List all runs:

```bash
curl -s http://localhost:8000/evaluations/runs \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" | python3 -m json.tool
```

View trace scores for a specific trace (e.g. the RAG pipeline):

```bash
curl -s http://localhost:8000/evaluations/trace-scores/a1b2c3d4-0002-4000-8000-000000000001 \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" | python3 -m json.tool
```

List all scores with filters:

```bash
# All scores for task_completion metric
curl -s "http://localhost:8000/evaluations/trace-scores?name=task_completion" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" | python3 -m json.tool

# Only failed scores
curl -s "http://localhost:8000/evaluations/trace-scores?status=FAILED" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" | python3 -m json.tool
```

Check analytics (after runs complete):

```bash
# Score summary per metric
curl -s http://localhost:8000/evaluations/analytics/trace-scores/summary \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" | python3 -m json.tool

# Score distribution for task_completion
curl -s "http://localhost:8000/evaluations/analytics/trace-scores/distribution?metric_name=task_completion" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" | python3 -m json.tool
```

### Things to Verify

1. **Run lifecycle** — Status transitions from PENDING to RUNNING to COMPLETED
2. **Score creation** — Each trace+metric pair produces a `trace_score` row with `source: AUTOMATED`
3. **Failed metrics** — If a metric fails (e.g. LLM timeout), the score has `status: FAILED`, `value: null`, and a reason explaining the failure
4. **Multiple metrics** — Batch run with 3 metrics on 2 traces should produce 6 score rows
5. **Filter accuracy** — Filtered run with `status: COMPLETED` should skip the error trace (`04`)
6. **Sampling** — Run with `sampling_rate: 0.5` on 6 traces should evaluate ~3 traces
7. **Worker logs** — Check `make logs` for `metric_completed` and `eval_run_completed` log entries

---

## Cleanup

To remove all seed data without dropping the database, use batch delete:

```bash
API_KEY="sk_pp_YOUR_KEY_HERE"
PROJECT="my-dev-project"

curl -s -X POST http://localhost:8000/traces/batch/delete \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Project-Name: $PROJECT" \
  -d '{
    "trace_ids": [
      "a1b2c3d4-0001-4000-8000-000000000001",
      "a1b2c3d4-0002-4000-8000-000000000001",
      "a1b2c3d4-0003-4000-8000-000000000001",
      "a1b2c3d4-0004-4000-8000-000000000001",
      "a1b2c3d4-0005-4000-8000-000000000001",
      "a1b2c3d4-0007-4000-8000-000000000001",
      "a1b2c3d4-0008-4000-8000-000000000001"
    ]
  }' | python3 -m json.tool
```

Or to drop everything and start fresh:

```bash
make down
docker volume rm pandaprobe_postgres-data
make up
```

---

## Interpreting Session-Level Metrics

Session evaluation produces two complementary scores that together give a complete picture of agent performance across a session (all traces sharing a `session_id`).

### `agent_reliability` (0–1, higher = safer)

Measures **worst-case failure risk**. Uses max-compose aggregation to surface the single most dangerous signal per trace, then applies top-k tail risk to focus on the worst traces. A single catastrophic trace will drag this score down even if every other trace is perfect.

**Read it as:** "Can I trust this agent not to fail?"

### `agent_consistency` (0–1, higher = more stable)

Measures **overall behavioral stability**. Uses weighted RMS aggregation where situational penalties (tool misuse, incoherence, looping) amplify confidence uncertainty. Penalizes sessions with many moderate issues even when no individual trace is catastrophic.

**Read it as:** "Does this agent perform smoothly and predictably?"

### Reading the Two Together

| Reliability | Consistency | Interpretation |
|---|---|---|
| HIGH | HIGH | Healthy agent — no failures, stable behavior. |
| HIGH | LOW | No catastrophic failures, but sustained moderate degradation across traces (e.g. slightly wrong tool usage everywhere). Investigate systemic issues. |
| LOW | HIGH | One or few traces failed badly while the rest were fine. The agent is generally stable but has edge-case vulnerabilities. Inspect flagged traces. |
| LOW | LOW | Widespread problems — the agent is both failing and behaving erratically. Likely looping, misusing tools, or incoherent across multiple traces. |
| MODERATE | HIGH | A persistent but non-critical issue (e.g. tool correctness at ~0.5) affects every trace uniformly. The agent is consistent but has a systematic weakness. |

### Underlying Signals

Both metrics aggregate the same four trace-level signals (inverted to risk):

| Signal | What it captures |
|---|---|
| `confidence` | Agent decisiveness — did the LLM appear confident in its actions? |
| `loop_detection` | Repetition — is the agent stuck repeating similar outputs? |
| `tool_correctness` | Tool usage — are the right tools called with correct arguments? |
| `coherence` | Input-output alignment — does the agent's response relate to its input? |

Default weights: confidence=1.0, loop_detection=1.0, tool_correctness=0.8, coherence=1.0. These can be overridden per eval run via the `signal_weights` field in the request body.

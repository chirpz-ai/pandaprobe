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

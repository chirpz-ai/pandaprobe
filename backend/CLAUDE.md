# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The repo-wide `CLAUDE.md` at the project root covers monorepo layout, the two-plane API model, backend domain layering, and shared conventions. This file adds the backend-specific details that are easy to get wrong without reading several files.

## Commands

All targets are exposed at the repo root (`make backend-*`) and as host-side targets in `backend/Makefile`. From inside `backend/`:

| Goal | Command |
|---|---|
| Install (locked) | `uv sync --frozen` |
| API server (host) | `make dev` — uvicorn on `:8000` with reload, `APP_ENV=development` |
| Celery worker (host) | `make worker` — needs Redis on `:6379` and Postgres on `:5432` |
| Lint / format | `make lint` / `make format` (ruff over `app/` and `tests/`) |
| Unit tests (host, no infra) | `make test-unit` (or `uv run --group test pytest tests/unit/ -v`) |
| Single unit test | `uv run --group test pytest tests/unit/test_traces.py::test_name -v` |
| Integration tests | From repo root: `make test-integration` — spins up `docker-compose.test.yml` (Postgres :5433, Redis :6380), runs `tests/integration/`, tears down with `-v` |
| New migration | `make migration msg="describe change"` — runs `alembic revision --autogenerate` against **local** Postgres on `:5432` |
| Apply migrations | `make migrate` (auto-applied on `make up` via Docker entrypoint) |

To run integration tests against an already-running test stack: set `POSTGRES_PORT=5433 POSTGRES_DB=pandaprobe_test_db REDIS_PORT=6380` and run `pytest tests/integration/`. `tests/conftest.py` already wires these env vars + `APP_ENV=test` + `CELERY_TASK_ALWAYS_EAGER=true`.

## Two auth dependencies — pick the right one

`app/api/dependencies.py` exposes three dependencies. Routes must pick deliberately:

- `get_api_context` — **management plane**. Bearer JWT only. Use for `/user`, `/organizations`, `/projects`, `/api-keys`, `/subscriptions`. Returns `ApiContext` with `organization` always set and `project` always `None`.
- `get_data_plane_context` — **data plane**. Accepts Bearer JWT (with `X-Project-ID`) **or** `X-API-Key` (with `X-Project-Name`). **When both are sent, API key wins** — this is intentional to prevent failures when Swagger UI sends a stale JWT alongside a valid key.
- `require_project` — thin wrapper around `get_data_plane_context` that 422s if `ctx.project is None`. Use this on every `/traces`, `/sessions`, `/evaluations` handler.

`_resolve_jwt` JIT-provisions: upserts the user from the IdP claims, auto-creates "My Organization" on first sign-in (plan = DEVELOPMENT when auth is disabled, else default tier), and on new-user creation enqueues welcome/follow-up emails + CRM sync via Celery. Routes get the resolved org/user via `ApiContext` — they should never re-query identity themselves.

`_resolve_api_key` resolves projects by *name* within the API key's org and **auto-creates the project if missing**. This is why SDK clients can call `POST /traces` with any new `X-Project-Name`.

## Celery worker: NullPool + per-task asyncio.run

`app/infrastructure/queue/tasks.py` has a critical pattern documented in its module docstring — don't deviate:

- Worker uses a **dedicated `NullPool` engine** (`_worker_engine`), not the request-path pool from `infrastructure/db/engine.py`. Every task creates a fresh connection via `_worker_session()` and discards it. Reusing a pooled connection across `asyncio.run()` calls causes `"attached to a different loop"` errors because each `asyncio.run()` creates a new event loop.
- Each Celery task body is a sync function that immediately calls `asyncio.run(_async_helper(...))`. Don't add async Celery tasks — use this pattern.
- **Heavy imports go inside the task function**, not at module top. This keeps worker bootup fast and avoids importing FastAPI/auth code into the worker process.

### Dispatcher + per-org worker fanout

For periodic jobs that touch many orgs (usage sync, overage billing, eval monitors), the pattern is **one dispatcher task that queries eligible IDs and fans out one sub-task per org/monitor**:

- `dispatch_sync_usage` → fans out `sync_single_org_usage(org_id)` per active org
- `dispatch_overage_billing` → fans out `bill_single_org(org_id)` per paid active org (rate-limited to `80/s` to stay under Stripe's `100/s` live cap)
- `dispatch_hobby_reset` → fans out `reset_single_hobby_org(org_id)`
- `check_eval_monitors` → fans out `process_single_monitor(monitor_id, project_id)` (and uses a Redis lock `check_eval_monitors` with `timeout=60` so only one beat worker drives the tick)

When adding new periodic work, follow the same shape — failures stay isolated to a single org, and workers parallelise across slots.

### Beat schedule

Configured in `infrastructure/queue/celery_app.py` using `RedBeatScheduler` (Redis-backed; no on-disk schedule file). Current cadence: eval monitors and usage sync every 5 min; overage billing and hobby reset every 6 hours; invitation expiry every hour.

## Auth adapter selection

`infrastructure/auth/adapters.py::get_auth_adapter()` dispatches:
- `AUTH_ENABLED=false` → `DevelopmentAdapter` (no-op JWT verify, returns a fixed dev identity). Allowed **only** in `APP_ENV=development` — `Settings._apply_environment_settings` forces `AUTH_ENABLED=true` everywhere else and logs an override warning.
- `AUTH_PROVIDER=firebase` → `FirebaseAdapter` (uses Firebase Admin SDK + ADC; `GOOGLE_CLOUD_PROJECT` required)
- `AUTH_PROVIDER=supabase` (default) → `SupabaseAdapter` (uses `SUPABASE_URL` + `SUPABASE_KEY`)

Adapters expose a single `verify_token(token) -> Claims` method called via `asyncio.to_thread` since IdP SDKs are sync.

## Settings: env-aware defaults

`Settings._apply_environment_settings` (`app/registry/settings.py`) overrides `DEBUG`, `LOG_LEVEL`, `LOG_FORMAT` per environment **only when the env var is not explicitly set**. So `LOG_LEVEL=DEBUG` in `.env.production` would still win, but the default behaviour gives you JSON `WARNING` logs in prod and console `DEBUG` logs in dev.

The lifespan in `main.py` calls `_validate_stripe_settings()` which **fails fast at startup** if `STRIPE_SECRET_KEY` or `STRIPE_WEBHOOK_SECRET` are missing in staging/production. Don't gate this behind a flag — it's intentional.

## Domain errors, not HTTPException

Raise subclasses of `PandaProbeError` (`registry/exceptions.py`) — `NotFoundError`, `AuthenticationError`, `AuthorizationError`, `ConflictError`, `ValidationError`, `QuotaExceededError`, `OrgLimitReachedError`. The handler in `main.py` translates them to `{"detail": "..."}` JSON with the right status code. Routes that raise `HTTPException` directly bypass this and break the error contract — use the domain exceptions.

Pydantic request-body validation errors are reshaped by `validation_exception_handler` into `{"detail": "Validation error", "errors": [{field, message}, ...]}` — clients depend on this shape.

## Domain entities vs ORM models

Repositories in `infrastructure/db/repositories/` return **core domain entities** (Pydantic models in `app/core/*/entities.py`), not SQLAlchemy `*Model` rows. Services and routes only see entities. If you add a column to a `*Model`, also add it to the entity and the repo mapping — otherwise the field is invisible to callers.

`get_db_session` (`infrastructure/db/engine.py`) is the per-request session dependency. It auto-`commit()`s on success and `rollback()`s on exception. Don't sprinkle `await session.commit()` at the end of route handlers — let the dependency handle it. Workers, in contrast, **must** commit explicitly because they don't go through this dependency.

## Integration test mechanics

`tests/integration/conftest.py` does several non-obvious things — read it before writing new integration tests:

- **`nest_asyncio.apply()`** at import time so Celery's `asyncio.run(...)` works inside the pytest-asyncio loop (eager mode).
- **TRUNCATE-based isolation**, not transaction rollback. The Celery task creates its own session/connection (matching real worker behaviour), so wrapping each test in a transaction would hide its commits from the test code. After each test, every table is `TRUNCATE ... CASCADE`d and the async engine pool is `dispose()`d so pooled connections don't leak into the next test's event loop.
- **Fixed seed UUIDs** (`TEST_ORG_ID`, `TEST_PROJECT_ID`) so every fixture in a test shares the same identity.
- **`autouse` dep overrides** replace `get_db_session`, `require_project`, and `get_redis` for every test. The overridden `require_project` returns a pre-built `ApiContext` — no auth roundtrip.
- **Redis `FLUSHDB`** runs at the end of every test so rate-limiter counters, eval locks, and usage counters don't bleed across tests.

If you need a test that exercises auth resolution itself (not bypassing it), override only `get_db_session` and `get_redis` and let `require_project` run for real.

## Conventions

- Ruff: `line-length = 119`, Google docstrings (`D`), `B`/`ERA` rules on. `D203`/`D213`/`B904`/`B008`/`D107`/`E501`/`F401` are intentionally ignored. `unfixable = ["B"]` — bugbear findings are surfaced but not auto-fixed.
- `tests/*` get `D100`/`D103`/`D104` waived; `__init__.py` files get `E402`/`D104` waived.
- API keys are stored hashed (`registry/security.py::hash_api_key`); never log or persist the raw key — only the prefix shown in `IdentityRepository`.
- New tables / column changes require an Alembic migration **and** an updated ORM model. `migration` runs autogenerate against the local Postgres on `:5432` — bring up `make up` (or just the postgres service) first.
- The only required runtime env vars in dev are Postgres/Redis connection vars; LLM, Stripe, Resend, Attio, PostHog keys are all optional and the corresponding services no-op when unset (`is_configured()` checks).

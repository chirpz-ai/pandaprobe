# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

PandaProbe is a monorepo with two top-level apps and Docker Compose orchestration at the root:

- `backend/` — FastAPI service, Celery worker/beat, Alembic migrations (Python 3.12+, managed via `uv`)
- `frontend/` — Next.js 16 + React 19 dashboard (TypeScript, yarn)
- `docker-compose.yml` — production / public-image compose used by `./start.sh`
- `docker-compose.dev.yml` — build-from-source dev compose (hot reload via bind mounts)
- `docker-compose.test.yml` — Postgres 5433 + Redis 6380 for backend integration tests
- Root `Makefile` — single entry point that delegates to `backend/Makefile` and `frontend/Makefile`. Run `make help` to list every target.

## Common commands

All commands are driven from the root Makefile. Targets are prefixed `backend-*` or `frontend-*`; combined targets exist for installs/lint/format/tests.

| Goal | Command |
|---|---|
| Install everything | `make install` |
| Full dev stack in Docker (hot reload) | `make up` / `make down` / `make restart` |
| Tail service logs | `make logs` (or `logs-app`, `logs-worker`, `logs-beat`, `logs-frontend`) |
| Run backend + frontend on host | `make dev` (also: `make worker` for Celery) |
| Backend dev only | `make backend-dev` (uvicorn with reload on :8000) |
| Frontend dev only | `make frontend-dev` (`yarn dev`) |
| Lint / format / typecheck | `make lint`, `make format`, `make typecheck` |
| Backend unit tests | `make backend-test-unit` (host, no infra) |
| Backend integration tests | `make test-integration` (spins up `docker-compose.test.yml` on ports 5433/6380, tears down after) |
| Frontend unit tests (Jest) | `make frontend-test-unit` |
| Frontend E2E (Playwright) | `make frontend-e2e-install` once, then `make frontend-test-e2e` |
| All tests | `make test-all` |

Run a single backend test:
```bash
cd backend && uv run --group test pytest tests/unit/test_traces.py::test_name -v
```
For integration tests, set the same env vars the Makefile uses (`POSTGRES_PORT=5433 POSTGRES_DB=pandaprobe_test_db REDIS_PORT=6380`) and target `tests/integration/`.

Run a single frontend Jest test:
```bash
cd frontend && yarn test path/to/file.test.ts
```

Database migrations (auto-applied on `make up` via Docker entrypoint):
- New migration: `make migration msg="describe change"` — runs `alembic revision --autogenerate` against local Postgres.
- Apply: `make migrate`.

## Architecture

### Two-plane API model

The FastAPI app exposes a single `/v1` router (`backend/app/api/v1/router.py`) but routes split into two authentication regimes (see `backend/app/api/dependencies.py`):

- **Management plane** — Bearer JWT from the configured IdP (Supabase or Firebase, selected by `AUTH_PROVIDER`). Used by the frontend for user, organization, project, billing, and API-key management.
- **Data plane** — Org-scoped API keys via `X-API-Key` + `X-Project-Name` headers. Used by SDK clients to send traces/spans/evaluations. The project is resolved by name inside the org and auto-created if missing.

`get_api_context` covers management; `require_project` accepts either a JWT with `X-Project-ID` or an API key with `X-Project-Name`. `RequestContextMiddleware` attaches an `X-Request-ID` and structured request logs. Rate limiting is enforced via `slowapi`.

`AUTH_ENABLED=false` disables JWT verification for local dev (the lifespan logs a prominent warning). In staging/production the app fails fast if Stripe keys are missing.

### Backend layering

`backend/app/` follows a domain-oriented layout — do not flatten it:

- `api/` — FastAPI routers, middleware, request context, rate limit. Routes only orchestrate; business logic belongs in services.
- `services/` — Use-case orchestration (`trace_service`, `eval_service`, `identity_service`, `billing_service`, `analytics_service`, `usage_service`, `crm_service`, `email_service`). Services depend on repositories, not on each other's internals.
- `core/` — Domain entities and per-domain repository protocols (`traces/`, `evals/`, `identity/`, `billing/`). `evals/metrics/` holds LLM-as-judge metric definitions; `evals/cadence.py` schedules recurring eval runs.
- `infrastructure/` — Adapters for external systems:
  - `auth/` — `base.AuthAdapter` + `firebase.py`, `supabase.py`, `development.py` (no-op). Selected via `get_auth_adapter()`.
  - `db/` — SQLAlchemy async engine, ORM models (`models.py`), and `repositories/` (concrete repos returning core entities).
  - `queue/` — `celery_app.py` (broker = Redis) and `tasks.py` (ingestion and eval workers).
  - `redis/` — async client + pool.
  - `llm/` — LiteLLM-based judge engine.
- `registry/` — Cross-cutting: `settings.py` (pydantic-settings, env-driven), `exceptions.py` (domain errors → JSON), `constants.py`, `security.py` (API-key hashing).
- `main.py` — composition root: lifespan hooks, CORS, middleware order, exception handlers, router include, Scalar docs at `/scalar`.

Ingestion path: SDK `POST /traces` → router enqueues to Redis → Celery worker persists trace + spans (`backend/app/infrastructure/queue/tasks.py`). Evaluations follow the same pattern, with the worker calling LiteLLM and writing the verdict.

### Frontend structure (`frontend/src/`)

- `app/` — Next.js App Router. Auth lives under `(auth)/`. Authenticated routes are nested under `org/[orgId]/project/[projectId]/` — when adding pages, follow this org/project segment pattern so the active context resolves correctly.
- `lib/api/` — One module per backend resource (`traces.ts`, `evaluations.ts`, …) all built on `client.ts`, which is configured via `configureAuth({getToken, forceRefreshToken, getOrgId, getProjectId, onUnauthorized})` at provider mount. The client injects the active org/project headers automatically — do not hand-build URLs that bypass it.
- `lib/auth/` — Firebase client + `auth-service` wrapper. The provider is wired in `components/providers/`.
- `lib/query/` — TanStack Query client and centralized `keys.ts`. Use the helpers in `keys.ts` for cache keys rather than inline arrays so invalidations stay coherent.
- `components/features/` — Page-level feature components (tables, sidebars, waterfalls).
- `components/ui/` — Radix-based primitives.
- `__tests__/` — Jest tests mirror the structure under `src/lib`. `__mocks__/` provides MSW + module mocks. E2E tests live in `frontend/e2e/`.

### Configuration

Backend reads `.env.${APP_ENV}` (e.g. `backend/.env.development`) via pydantic-settings. Key env vars: `APP_ENV`, `AUTH_PROVIDER` (`supabase`/`firebase`), `AUTH_ENABLED`, Postgres/Redis connection vars, Stripe keys, LiteLLM credentials. Frontend reads `frontend/.env.development`; `NEXT_PUBLIC_API_URL` is the only required public var.

Test suite sets `APP_ENV=test`, `CELERY_TASK_ALWAYS_EAGER=true`, and points at the test-compose ports (see `backend/tests/conftest.py`).

## Conventions worth knowing

- Ruff is configured at `backend/pyproject.toml` with `line-length = 119`, Google docstring convention, and `B`/`ERA`/`D` rules enabled. `make backend-format` runs `ruff format`.
- Frontend uses Prettier + ESLint (`eslint-config-next`). `make frontend-format-check` is what CI runs; commits with unformatted code will be rejected.
- Migrations are auto-generated against the **local** Postgres on port 5432, not the test DB. Bring up `make up` (or just the postgres service) before `make migration`.
- Integration tests **must not** be pointed at the dev database — the Makefile sets `POSTGRES_PORT=5433`/`REDIS_PORT=6380` and tears the stack down with `-v` after the run to guarantee isolation.
- The repo's frontend `CLAUDE.md` (`frontend/CLAUDE.md`) is a one-line `@AGENTS.md` import; that file does not currently exist, so there is no additional frontend-specific guidance to load beyond this file.

# PandaProbe

Open-source, multi-tenant agent tracing and evaluation service. Trace agentic workflows from any framework, evaluate them with LLM-as-a-judge metrics, and query results via a REST API.

## Quick Start

```bash
# 1. Configure environment
cp backend/.env.example backend/.env.development
# Edit backend/.env.development — add your Supabase credentials and LLM provider keys

# 2. Start all services
make up

# 3. Open http://localhost:8000/scalar for API references
```

## Architecture

```mermaid
sequenceDiagram
    participant Client as 📡 SDK / HTTP Client
    participant API as ⚡ FastAPI
    participant Auth as 🔐 Auth Service
    participant IdP as 🌐 Supabase / Firebase
    participant Identity as 👥 Identity Service
    participant Trace as 🫆 Trace Service
    participant Eval as 🧪 Eval Service
    participant DB as 🗄️ PostgreSQL
    participant Redis as 📮 Redis
    participant Worker as ⚙️ Celery Worker
    participant LLM as 🤖 LLM Engine (LiteLLM)

    Note over Client,API: Management Plane (Bearer token)
    Client->>API: Authorization: Bearer <idp_token>
    API->>Auth: Verify token
    Auth->>IdP: Validate with provider
    IdP-->>Auth: User identity
    Auth-->>API: Authenticated user
    API->>Identity: /user, /organizations, /projects
    Identity->>DB: Read / write
    DB-->>Identity: Result
    Identity-->>Client: Response

    Note over Client,API: Data Plane (API key)
    Client->>API: X-API-Key + X-Project-Name
    API->>Identity: Resolve org & project
    Identity-->>API: Project context

    API->>Trace: POST /traces
    Trace->>Redis: Enqueue ingestion job
    Redis-->>Client: 202 Accepted
    Redis->>Worker: Pick up job
    Worker->>DB: Persist trace + spans

    API->>Trace: GET /traces, /sessions
    Trace->>DB: Query with filters
    DB-->>Trace: Rows
    Trace-->>Client: Paginated response

    API->>Eval: POST /evaluations
    Eval->>Redis: Enqueue eval job
    Redis-->>Client: 202 Accepted
    Redis->>Worker: Pick up job
    Worker->>LLM: LLM-as-a-judge call
    LLM-->>Worker: Verdict + score
    Worker->>DB: Persist evaluation result
```

## Multi-Tenant Hierarchy

```
User ──(Membership)──► Organization ──► Project ──► Trace / Evaluation
                                   └──► API Key (org-scoped)

Trace ──(session_id)──► Session (implicit grouping, no dedicated table)
```

- **Users** authenticate via an external IdP (Supabase or Firebase).
- **Organizations** contain **Projects**. Users join orgs via **Memberships** (OWNER / ADMIN / MEMBER).
- **API Keys** are org-scoped with `sk_pp_` prefix. The SDK specifies the target project via `X-Project-Name` header. Projects are auto-created on first trace.

## Auth Strategy

| Route group | Auth method | Header |
|---|---|---|
| Management (`/user`, `/organizations`, `/projects`) | IdP token | `Authorization: Bearer <token>` |
| Data plane (`/traces`, `/evaluations`, `/sessions`) | API key | `X-API-Key` + `X-Project-Name` |

## Services

| Service | Description | Port |
|---|---|---|
| **app** | FastAPI application server | 8000 |
| **worker** | Celery background worker | — |
| **postgres** | PostgreSQL 16 | 5432 |
| **redis** | Redis 7 (broker + cache) | 6379 |

## Development

```bash
make install          # Install backend deps via uv
make up               # Start all services (Docker)
make down             # Stop all services
make dev              # Run API locally with hot-reload
make worker           # Run Celery worker locally

make lint             # Ruff linter
make format           # Auto-format code
make migration msg="" # Generate Alembic migration
make migrate          # Apply migrations

make test-unit        # Run unit tests
make test-integration # Run integration tests (spins up test DB)
make test-all         # Run everything
make help             # Show all available commands
```

> [!NOTE]
> **Database migrations** are auto-applied on `make up` via the Docker entrypoint.
> 
> To generate a new migration after model changes:
> ```bash
> make migration msg="describe change"
> ```
> To manually apply migrations:
> ```bash
> make migrate
> ```

## Environment Variables

See [`backend/.env.example`](backend/.env.example) for the full list. Key variables:

| Variable | Description |
|---|---|
| `AUTH_PROVIDER` | `supabase` or `firebase` |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon/public key |
| `GOOGLE_CLOUD_PROJECT` | GCP project for Firebase + Vertex AI |
| `EVAL_LLM_MODEL` | Default eval model (LiteLLM format) |
| `OPENAI_API_KEY` | OpenAI credentials |

## Authors

Built by Chirpz AI team. Contact sina@chirpz.ai for all enquiries.

## License

PandaProbe is licensed under Apache 2.0 — see [LICENSE](LICENSE) for details.

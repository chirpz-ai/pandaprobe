<div align="center">
  <a href="https://pandaprobe.com" target="_blank" rel="noopener noreferrer">
    <img alt="PandaProbe Logo" src="docs/assets/PandProbe-1.png" width="100%">
  </a>
</div>

<p align="center">
  PandaProbe is an open source agent engineering platform.<br>
  It helps teams collaboratively develop, monitor, evaluate, and debug AI agents.<br>
  You can use PandaProbe cloud (under dev) or self host the service.
</p>

<p align="center">
  <a href="https://pandaprobe.com/" target="_blank"><img src="https://img.shields.io/badge/PandaProbe_Cloud-0066FF" alt="PandaProbe Cloud"></a>
  <a href="https://pandaprobe.com/" target="_blank"><img src="https://img.shields.io/badge/Docs-0066FF" alt="Docs"></a>
  <a href="https://x.com/PandaProbe" target="_blank"><img src="https://img.shields.io/twitter/follow/PandaProbe?style=social" alt="Follow on X"></a>
</p>

<p align="center">
  <a href="https://github.com/chirpz-ai/pandaprobe/actions/workflows/build.yml"><img src="https://github.com/chirpz-ai/pandaprobe/actions/workflows/build.yml/badge.svg" alt="Build"></a>
  <a href="https://github.com/chirpz-ai/pandaprobe/actions/workflows/lint.yml"><img src="https://github.com/chirpz-ai/pandaprobe/actions/workflows/lint.yml/badge.svg" alt="Lint"></a>
  <a href="https://github.com/chirpz-ai/pandaprobe/actions/workflows/test-unit.yml"><img src="https://github.com/chirpz-ai/pandaprobe/actions/workflows/test-unit.yml/badge.svg" alt="Unit Tests"></a>
  <a href="https://github.com/chirpz-ai/pandaprobe/actions/workflows/test-integration.yml"><img src="https://github.com/chirpz-ai/pandaprobe/actions/workflows/test-integration.yml/badge.svg" alt="Integration Tests"></a>
  <a href="https://github.com/chirpz-ai/pandaprobe/actions/workflows/codeql.yml"><img src="https://github.com/chirpz-ai/pandaprobe/actions/workflows/codeql.yml/badge.svg" alt="CodeQL"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"></a>
</p>

---

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

## Auth

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

## Contributing

We welcome contributions! Please read the [Contributing Guide](CONTRIBUTING.md) for details on how to set up your environment, run tests, and submit pull requests.

## Authors

Built by the [Chirpz AI](https://github.com/chirpz-ai) team. Contact sina@chirpz.ai for enquiries.

## License

PandaProbe is licensed under Apache 2.0 — see [LICENSE](LICENSE) for details.

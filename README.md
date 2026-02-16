# Opentracer

Open-source agent tracing and evaluation service.

## Quick Start

```bash
# 1. Copy environment config
cp .env.example .env.development

# 2. Start all services (API, worker, Postgres, Redis)
make up

# 3. Run database migrations
make migrate

# 4. API is available at http://localhost:8000
#    Docs at http://localhost:8000/docs
```

## Local Development (without Docker)

```bash
make install          # install dependencies
make dev              # run API with hot-reload
make worker           # run Celery worker (separate terminal)
make migrate          # apply database migrations
make test             # run test suite
make lint             # check code style
```

## Architecture

Opentracer follows a Domain-Driven Design (DDD) layered architecture:

| Layer | Path | Role |
|-------|------|------|
| **API** | `app/api/` | FastAPI routers and request/response schemas |
| **Core** | `app/core/` | Pure domain entities and abstract interfaces |
| **Registry** | `app/registry/` | Settings, security, constants, exceptions |
| **Infrastructure** | `app/infrastructure/` | Database repos, Redis queue, LLM providers |
| **Services** | `app/services/` | Orchestration between Core and Infrastructure |

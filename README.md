<div align="center">
  <a href="https://pandaprobe.com/" target="_blank" rel="noopener noreferrer">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo/dark.png">
      <source media="(prefers-color-scheme: light)" srcset="docs/assets/logo/light.png">
      <img alt="PandaProbe Logo" src="docs/assets/logo/light.png" width="80%">
    </picture>
  </a>
</div>

<div align="center">
  <img src="docs/assets/heading.svg" alt="open source agent engineering platform. By Chirpz AI" width="700"/>
</div>


<p align="center">
  <a href="https://app.pandaprobe.com/" target="_blank"><img src="https://img.shields.io/badge/PandaProbe_Cloud-0066FF" alt="PandaProbe Cloud"></a>
  <a href="https://docs.pandaprobe.com/" target="_blank"><img src="https://img.shields.io/badge/Docs-0066FF" alt="Docs"></a>
  <a href="https://x.com/PandaProbe" target="_blank"><img src="https://img.shields.io/twitter/follow/PandaProbe?style=social" alt="Follow on X"></a>
</p>

<p align="center">
  <a href="https://pypi.org/project/pandaprobe/" alt="PyPI Downloads"><img src="https://static.pepy.tech/badge/pandaprobe" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"></a>
  <a href="https://www.pandaprobe.com/" alt="Website"><img src="https://img.shields.io/badge/made by-Chirpz AI-blue" /></a>
  <a href="https://discord.gg/A2VfrRhx"><img src="https://img.shields.io/discord/1486405147893436426?label=Discord&logo=discord&logoColor=white&style=flat-square" alt="Discord"></a>
  <br/>
  <a href="https://github.com/chirpz-ai/pandaprobe/actions/workflows/build.yml"><img src="https://github.com/chirpz-ai/pandaprobe/actions/workflows/build.yml/badge.svg" alt="Build"></a>
  <a href="https://github.com/chirpz-ai/pandaprobe/actions/workflows/lint.yml"><img src="https://github.com/chirpz-ai/pandaprobe/actions/workflows/lint.yml/badge.svg" alt="Lint"></a>
  <a href="https://github.com/chirpz-ai/pandaprobe/actions/workflows/test-unit.yml"><img src="https://github.com/chirpz-ai/pandaprobe/actions/workflows/test-unit.yml/badge.svg" alt="Unit Tests"></a>
  <a href="https://github.com/chirpz-ai/pandaprobe/actions/workflows/test-integration.yml"><img src="https://github.com/chirpz-ai/pandaprobe/actions/workflows/test-integration.yml/badge.svg" alt="Integration Tests"></a>
  <a href="https://github.com/chirpz-ai/pandaprobe/actions/workflows/codeql.yml"><img src="https://github.com/chirpz-ai/pandaprobe/actions/workflows/codeql.yml/badge.svg" alt="CodeQL"></a>
</p>

## What is PandaProbe?

PandaProbe is an open source agent engineering platform for tracing, evaluating, and improving AI agents. It helps you understand what happened, check whether the work succeeded, and give your agent feedback it can use to make fewer mistakes.

- **Trace** captures model calls, tool use, inputs, outputs, errors, latency, and usage. Group related executions into sessions to follow a conversation or task.
- **Evaluate** measures the quality of traces and sessions, records programmatic scores, and identifies failures that need attention.
- **Reflect** brings failure evidence back to your agent through a persistent rule filesystem. The agent proposes reusable guidance; independent validation tests changes before accepting them as shared rules for future runs.

Python and TypeScript SDKs connect to supported agent frameworks and model providers while preserving your existing agent, tools, and application logic. Start with tracing, add evaluations suited to your task, and enable Reflect when you have reproducible cases and outcome checks.

Use [PandaProbe Cloud](https://app.pandaprobe.com/) for a managed deployment, or self-host the community project using the instructions below.

## Documentation

Explore the docs:

- [Tracing quickstart](https://docs.pandaprobe.com/tracing/get-started/quickstart)
- [Evaluation quickstart](https://docs.pandaprobe.com/evaluation/get-started/quickstart)
- [Reflect quickstart](https://docs.pandaprobe.com/reflect/quickstart)

<p align="left">
  <a href="https://docs.pandaprobe.com/overview" target="_blank">
    <img alt="Documentation" src="https://img.shields.io/badge/Docs%20Overview-0066FF" />
  </a>
</p>

## PandaProbe Cloud

Managed deployment by the PandaProbe team, generous free-tier, no credit card required.

<p align="left">
  <a href="https://app.pandaprobe.com/" target="_blank">
    <img alt="Sign up for PandaProbe Cloud" src="https://img.shields.io/badge/%C2%BB%20Sign%20up%20for%20PandaProbe%20Cloud-0066FF" />
  </a>
</p>

## Self-host PandaProbe

> **Prerequisites:** [Docker](https://docs.docker.com/get-docker/) must be installed and running.

```bash
git clone https://github.com/chirpz-ai/pandaprobe.git
cd pandaprobe
./start.sh
```

Once running, open:
- **Dashboard** — http://localhost:3000
- **API reference** — http://localhost:8000/scalar

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

## Services

| Service | Description | Port |
|---|---|---|
| **frontend** | Next.js dashboard | 3000 |
| **app** | FastAPI application server | 8000 |
| **worker** | Celery background worker | — |
| **beat** | Celery Beat scheduler | — |
| **postgres** | PostgreSQL 16 | 5432 |
| **redis** | Redis 7 (broker + cache) | 6379 |

## Contributing

We welcome contributions! Please read the [Contributing Guide](CONTRIBUTING.md) for instructions on setting up your development environment, building from source, running tests, and submitting pull requests.

## Authors

Built by the [Chirpz AI](https://pandaprobe.com/about) team. Contact sina@pandaprobe.com for enquiries.

## License

PandaProbe is licensed under Apache 2.0 — see [LICENSE](LICENSE) for details.

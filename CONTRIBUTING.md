# Contributing to PandaProbe

Thank you for your interest in contributing to PandaProbe! This guide covers everything you need to set up your development environment, build from source, and submit changes.

PandaProbe is licensed under [Apache 2.0](LICENSE). By contributing, you agree that your contributions will be licensed under the same terms.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (for containerized development and integration tests)
- [Node.js](https://nodejs.org/) and [Yarn](https://yarnpkg.com/) (for the frontend)
- [Python 3.12+](https://www.python.org/) and [uv](https://docs.astral.sh/uv/) (for the backend)

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/<your-username>/pandaprobe.git
cd pandaprobe
```

### 2. Install Dependencies

All project commands are managed through the root **Makefile**. Run `make help` at any time to see every available target.

```bash
make install    # Install all dependencies (backend + frontend)
```

### 3. Configure Environment

```bash
cp backend/.env.example backend/.env.development
cp frontend/.env.example frontend/.env.development
```

Edit each `.env.development` file with any required credentials.

## Building from Source (Docker Compose)

The fastest way to get everything running with hot reload:

```bash
make up         # Build & start all services (API, worker, frontend, PostgreSQL, Redis)
make down       # Stop all services
make restart    # Restart all services
```

Once running, open:

- **Dashboard** — http://localhost:3000
- **API reference** — http://localhost:8000/scalar

### Viewing Logs

```bash
make logs            # Tail all service logs
make logs-app        # Tail backend logs only
make logs-worker     # Tail worker logs only
make logs-beat       # Tail beat scheduler logs only
make logs-frontend   # Tail frontend logs only
make ps              # Show running containers
```

## Running Locally (Outside Docker)

If you prefer running the backend and frontend directly on your host:

```bash
make dev        # Run backend API server + frontend dev server
make worker     # Run Celery worker
```

> PostgreSQL and Redis still need to be available (either via Docker or locally installed).

## Code Quality

Run linters and formatters **before** pushing:

```bash
make lint       # Run all linters (backend + frontend)
make format     # Auto-format all code
make typecheck  # Run TypeScript type checking
```

CI will reject PRs that have lint errors or unformatted code.

## Testing

```bash
make test-unit          # Run all unit tests (backend + frontend)
make test-integration   # Run backend integration tests (spins up test PostgreSQL + Redis)
make test-all           # Run everything (unit + integration + E2E)
```

Please add or update tests for any code changes you make.

## Database Migrations

> [!NOTE]
> **Database migrations** are auto-applied on `make up` via the Docker entrypoint.
> You only need to run migration commands manually when creating new migrations or applying them outside of Docker.

If your changes modify SQLAlchemy models, generate and include an Alembic migration:

```bash
make migration msg="describe your change"
```

To manually apply migrations:

```bash
make migrate
```

## Submitting a Pull Request

1. **Create a branch** from `main` with a descriptive name:

   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes** in small, focused commits.

3. **Verify everything passes** locally:

   ```bash
   make lint
   make test-unit
   ```

4. **Push** your branch and open a Pull Request against `main`.

5. **Fill out the PR template** — link related issues, describe your changes, and complete the checklist.

## PR Guidelines

- Keep pull requests focused on a single change.
- Use descriptive PR titles (e.g., "Add session analytics endpoint" not "Update code").
- Reference related issues with `Closes #123` in the PR description.
- Respond to review feedback promptly.

## Reporting Issues

Found a bug or have a feature idea? Please open an issue using the appropriate [issue template](https://github.com/chirpz-ai/pandaprobe/issues/new/choose).

## Questions?

If you have questions that aren't covered here, open a [discussion](https://github.com/chirpz-ai/pandaprobe/discussions) or reach out to the maintainers.

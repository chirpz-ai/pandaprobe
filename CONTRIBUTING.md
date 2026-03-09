# Contributing to PandaProbe

Thank you for your interest in contributing to PandaProbe! This guide will help you get started.

PandaProbe is licensed under [Apache 2.0](LICENSE). By contributing, you agree that your contributions will be licensed under the same terms.

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/<your-username>/pandaprobe.git
cd pandaprobe
```

### 2. Configure Environment

```bash
cp backend/.env.example backend/.env.development
# Edit backend/.env.development with your credentials (see the README for details)
```

### 3. Start Services

All project commands are managed through the root **Makefile**. Run `make help` at any time to see every available target.

```bash
make up         # Build and start all services (API, worker, PostgreSQL, Redis) via Docker Compose
make down       # Stop all services
make restart    # Restart all services
make logs       # Tail logs from all services
make ps         # Show running containers
```

The API will be available at `http://localhost:8000/scalar` once the services are up.

## Code Quality

Run the linter and formatter **before** pushing:

```bash
make lint       # Runs Ruff linter against app/ and tests/
make format     # Auto-formats code with Ruff
```

CI will reject PRs that have lint errors or unformatted code.

## Running Tests

```bash
make test-unit          # Unit tests (no external services required)
make test-integration   # Integration tests (spins up test Postgres + Redis automatically)
make test-all           # Runs both suites
```

Please add or update tests for any code changes you make.

## Database Migrations

If your changes modify SQLAlchemy models, generate and include an Alembic migration:

```bash
make migration msg="describe your change"
make migrate   # Apply the migration locally to verify it works
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

Found a bug or have a feature idea? Please open an issue using the appropriate [issue template](https://github.com/ChirpZ/pandaprobe/issues/new/choose).

## Questions?

If you have questions that aren't covered here, open a [discussion](https://github.com/ChirpZ/pandaprobe/discussions) or reach out to the maintainers.

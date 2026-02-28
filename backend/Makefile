.PHONY: install dev lint format migrate worker test-unit help

# -- Installation & environment -----------------------------------------------

install:  ## Install locked dependencies via uv
	pip install uv && uv sync --frozen

# -- Local development --------------------------------------------------------

dev:  ## Run the API server locally (outside Docker)
	APP_ENV=development uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:  ## Run the Celery worker locally
	APP_ENV=development uv run celery -A app.infrastructure.queue.celery_app worker --loglevel=info

# -- Code quality -------------------------------------------------------------

lint:  ## Run ruff linter
	uv run --group dev ruff check app/ tests/

format:  ## Auto-format code
	uv run --group dev ruff format app/ tests/

# -- Database -----------------------------------------------------------------

migration:  ## Auto-generate a new Alembic migration.  Usage: make migration msg="add users external_id"
	POSTGRES_HOST=localhost uv run alembic revision --autogenerate -m "$(msg)"

migrate:  ## Run Alembic migrations (head) against local Postgres
	POSTGRES_HOST=localhost uv run alembic upgrade head

# -- Testing ------------------------------------------------------------------

test-unit:  ## Run unit tests
	uv run --group test pytest tests/unit/ -v

# -- Help ---------------------------------------------------------------------

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

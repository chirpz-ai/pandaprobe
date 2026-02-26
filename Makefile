.PHONY: install dev lint format migrate up down logs worker test-unit test-integration test-all test-db-up test-db-down help

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

# -- Docker Compose (development) ---------------------------------------------

up:  ## Start all dev services
	docker compose -f docker-compose.dev.yml up --build -d

down:  ## Stop all dev services
	docker compose -f docker-compose.dev.yml down

logs:  ## Tail dev service logs
	docker compose -f docker-compose.dev.yml logs -f

logs-app:  ## Tail app logs only
	docker compose -f docker-compose.dev.yml logs -f app

logs-worker:  ## Tail worker logs only
	docker compose -f docker-compose.dev.yml logs -f worker

ps:  ## Show running containers
	docker compose -f docker-compose.dev.yml ps

restart:  ## Restart all dev services
	docker compose -f docker-compose.dev.yml restart

# -- Testing ------------------------------------------------------------------

test-unit:  ## Run unit tests
	uv run --group test pytest tests/unit/ -v

test-integration:  ## Start test stack, run integration tests, tear down
	docker compose -f docker-compose.test.yml up -d --wait
	POSTGRES_PORT=5433 POSTGRES_DB=pandaprobe_test_db REDIS_PORT=6380 \
		uv run --group test pytest tests/integration/ -v; \
	status=$$?; \
	docker compose -f docker-compose.test.yml down -v; \
	exit $$status

test-all:  ## Run unit + integration tests
	uv run --group test pytest tests/unit/ -v
	$(MAKE) test-integration

test-db-up:  ## Start the test PostgreSQL and Redis services
	docker compose -f docker-compose.test.yml up -d --wait

test-db-down:  ## Stop and remove the test services
	docker compose -f docker-compose.test.yml down -v

# -- Help ---------------------------------------------------------------------

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

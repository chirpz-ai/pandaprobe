.PHONY: install dev worker lint format migration migrate \
       up down logs logs-app logs-worker logs-beat ps restart \
       test-unit-backend test-unit \
       test-integration-backend test-integration \
       test-all test-db-up test-db-down help

# =============================================================================
#  PandaProbe Monorepo Makefile
#  Delegates backend-specific tasks to backend/Makefile.
#  Docker Compose orchestration lives here at the repo root.
# =============================================================================

# -- Backend delegates --------------------------------------------------------

install:  ## Install backend dependencies
	$(MAKE) -C backend install

dev:  ## Run the backend API server locally
	$(MAKE) -C backend dev

worker:  ## Run the backend Celery worker locally
	$(MAKE) -C backend worker

lint:  ## Run backend linter
	$(MAKE) -C backend lint

format:  ## Auto-format backend code
	$(MAKE) -C backend format

migration:  ## Auto-generate an Alembic migration.  Usage: make migration msg="..."
	$(MAKE) -C backend migration msg="$(msg)"

migrate:  ## Run Alembic migrations (head)
	$(MAKE) -C backend migrate

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

logs-beat:  ## Tail beat scheduler logs only
	docker compose -f docker-compose.dev.yml logs -f beat

ps:  ## Show running containers
	docker compose -f docker-compose.dev.yml ps

restart:  ## Restart all dev services
	docker compose -f docker-compose.dev.yml restart

# -- Testing ------------------------------------------------------------------

test-unit-backend:  ## Run backend unit tests
	$(MAKE) -C backend test-unit

test-integration-backend:  ## Run backend integration tests (starts test infra)
	docker compose -f docker-compose.test.yml up -d --wait
	cd backend && POSTGRES_PORT=5433 POSTGRES_DB=pandaprobe_test_db REDIS_PORT=6380 \
		uv run --group test pytest tests/integration/ -v; \
	status=$$?; \
	cd .. && docker compose -f docker-compose.test.yml down -v; \
	exit $$status

test-unit:  ## Run all unit tests
	$(MAKE) test-unit-backend

test-integration:  ## Run all integration tests
	$(MAKE) test-integration-backend

test-all:  ## Run all unit + integration tests
	$(MAKE) test-unit
	$(MAKE) test-integration

test-db-up:  ## Start the test PostgreSQL and Redis services
	docker compose -f docker-compose.test.yml up -d --wait

test-db-down:  ## Stop and remove the test services
	docker compose -f docker-compose.test.yml down -v

# -- Help ---------------------------------------------------------------------

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install dev worker lint format migration migrate \
       backend-install backend-dev backend-worker backend-lint backend-format \
       backend-test-unit backend-test-integration \
       frontend-install frontend-dev frontend-build frontend-lint \
       frontend-test-unit frontend-test-e2e frontend-test \
       up down logs logs-app logs-worker logs-beat logs-frontend ps restart \
       test-unit test-integration test-all test-db-up test-db-down help

# =============================================================================
#  PandaProbe Monorepo Makefile
#  Delegates tasks to backend/Makefile and frontend/Makefile.
#  Docker Compose orchestration lives here at the repo root.
# =============================================================================

# -- Backend targets ----------------------------------------------------------

backend-install:  ## Install backend dependencies
	$(MAKE) -C backend install

backend-dev:  ## Run the backend API server locally
	$(MAKE) -C backend dev

backend-worker:  ## Run the backend Celery worker locally
	$(MAKE) -C backend worker

backend-lint:  ## Run backend linter
	$(MAKE) -C backend lint

backend-format:  ## Auto-format backend code
	$(MAKE) -C backend format

backend-test-unit:  ## Run backend unit tests
	$(MAKE) -C backend test-unit

backend-test-integration:  ## Run backend integration tests (starts test infra)
	docker compose -f docker-compose.test.yml up -d --wait
	cd backend && POSTGRES_PORT=5433 POSTGRES_DB=pandaprobe_test_db REDIS_PORT=6380 \
		uv run --group test pytest tests/integration/ -v; \
	status=$$?; \
	cd .. && docker compose -f docker-compose.test.yml down -v; \
	exit $$status

# -- Frontend targets ---------------------------------------------------------

frontend-install:  ## Install frontend dependencies
	$(MAKE) -C frontend install

frontend-dev:  ## Run the frontend dev server locally
	$(MAKE) -C frontend dev

frontend-build:  ## Build frontend for production
	$(MAKE) -C frontend build

frontend-lint:  ## Run frontend linter
	$(MAKE) -C frontend lint

frontend-test-unit:  ## Run frontend unit tests
	$(MAKE) -C frontend test-unit

frontend-test-e2e:  ## Run frontend E2E tests
	$(MAKE) -C frontend test-e2e

frontend-test:  ## Run all frontend tests
	$(MAKE) -C frontend test

# -- Combined targets (both backend + frontend) ------------------------------

install:  ## Install all dependencies (backend + frontend)
	$(MAKE) backend-install
	$(MAKE) frontend-install

dev:  ## Run both backend API server and frontend dev server locally
	$(MAKE) backend-dev &
	$(MAKE) frontend-dev

lint:  ## Run all linters (backend + frontend)
	$(MAKE) backend-lint
	$(MAKE) frontend-lint

format:  ## Auto-format all code
	$(MAKE) backend-format

worker:  ## Run the backend Celery worker locally
	$(MAKE) backend-worker

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

logs-frontend:  ## Tail frontend logs only
	docker compose -f docker-compose.dev.yml logs -f frontend

ps:  ## Show running containers
	docker compose -f docker-compose.dev.yml ps

restart:  ## Restart all dev services
	docker compose -f docker-compose.dev.yml restart

# -- Testing ------------------------------------------------------------------

test-unit:  ## Run all unit tests (backend + frontend)
	$(MAKE) backend-test-unit
	$(MAKE) frontend-test-unit

test-integration:  ## Run all integration tests
	$(MAKE) backend-test-integration

test-all:  ## Run all unit + integration + E2E tests
	$(MAKE) test-unit
	$(MAKE) test-integration
	$(MAKE) frontend-test-e2e

test-db-up:  ## Start the test PostgreSQL and Redis services
	docker compose -f docker-compose.test.yml up -d --wait

test-db-down:  ## Stop and remove the test services
	docker compose -f docker-compose.test.yml down -v

# -- Help ---------------------------------------------------------------------

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install dev lint format migrate up down logs worker test help

# -- Installation & environment -----------------------------------------------

install:  ## Install dependencies via uv
	pip install uv && uv sync

# -- Local development --------------------------------------------------------

dev:  ## Run the API server locally (outside Docker)
	APP_ENV=development uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:  ## Run the Celery worker locally
	APP_ENV=development celery -A app.infrastructure.queue.celery_app worker --loglevel=info

# -- Code quality -------------------------------------------------------------

lint:  ## Run ruff linter
	ruff check app/ tests/

format:  ## Auto-format code
	ruff format app/ tests/

# -- Database -----------------------------------------------------------------

migrate:  ## Run Alembic migrations (head)
	alembic upgrade head

migration:  ## Auto-generate a new Alembic migration.  Usage: make migration msg="add traces table"
	alembic revision --autogenerate -m "$(msg)"

# -- Docker Compose -----------------------------------------------------------

up:  ## Start all services
	docker compose up --build -d

down:  ## Stop all services
	docker compose down

logs:  ## Tail service logs
	docker compose logs -f

# -- Testing ------------------------------------------------------------------

test:  ## Run the test suite
	pytest tests/ -v

# -- Help ---------------------------------------------------------------------

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

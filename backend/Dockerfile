FROM python:3.14.3-slim AS base

WORKDIR /app

ARG APP_ENV=production

ENV APP_ENV=${APP_ENV} \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# System deps: libpq (psycopg2), curl (healthcheck), pg client + redis
# tools (entrypoint connectivity checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    postgresql-client \
    redis-tools \
    && pip install --upgrade pip \
    && pip install uv \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from lockfile (cached unless either file changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

# Make scripts executable
RUN chmod +x /app/scripts/docker-entrypoint.sh

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser
RUN mkdir -p /app/logs

EXPOSE 8000

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

# Default: run the API server.  The worker service overrides CMD.
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

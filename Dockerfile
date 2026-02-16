FROM python:3.13.2-slim AS base

WORKDIR /app

ARG APP_ENV=production

ENV APP_ENV=${APP_ENV} \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# System dependencies (libpq for psycopg2, build-essential for C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && pip install --upgrade pip \
    && pip install uv \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached unless pyproject.toml changes)
COPY pyproject.toml .
RUN uv venv && . .venv/bin/activate && uv pip install -e .

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

#!/bin/bash
set -e

echo "=== Opentracer container starting ==="
echo "APP_ENV: ${APP_ENV:-development}"

# Load .env file if present (Docker Compose already injects env vars,
# but this covers standalone docker-run cases).
if [ -f ".env.${APP_ENV}" ]; then
    echo "Loading .env.${APP_ENV}"
    set -a
    # shellcheck source=/dev/null
    source ".env.${APP_ENV}"
    set +a
elif [ -f ".env" ]; then
    echo "Loading .env"
    set -a
    source ".env"
    set +a
fi

echo "Database host : ${POSTGRES_HOST:-not set}"
echo "Redis host    : ${REDIS_HOST:-not set}"
echo "Debug         : ${DEBUG:-false}"

exec "$@"

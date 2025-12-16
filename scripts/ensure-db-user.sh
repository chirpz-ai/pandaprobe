#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <environment>"
  echo "Environments: development, staging, production"
  exit 1
fi

ENV=$1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env.$ENV"

if [ -f "$ENV_FILE" ]; then
  echo "Loading environment variables from $ENV_FILE for database initialization"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "Warning: $ENV_FILE not found. Falling back to current environment for database initialization."
fi

POSTGRES_USER=${POSTGRES_USER:-postgres}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
POSTGRES_DB=${POSTGRES_DB:-food_order_db}

DOCKER_COMPOSE_BIN=${DOCKER_COMPOSE_BIN:-docker compose}
IFS=' ' read -r -a DC_CMD <<< "$DOCKER_COMPOSE_BIN"

echo "Waiting for PostgreSQL service to be ready..."
MAX_ATTEMPTS=30
SLEEP_SECONDS=2
attempt=1

until "${DC_CMD[@]}" exec -T db pg_isready -U postgres >/dev/null 2>&1; do
  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    echo "PostgreSQL service did not become ready in time."
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep "$SLEEP_SECONDS"
done

echo "Ensuring role '$POSTGRES_USER' and database '$POSTGRES_DB' exist"

role_escaped=${POSTGRES_USER//"/""}
role_escaped=${role_escaped//\'/''}
password_escaped=${POSTGRES_PASSWORD//\'/''}
db_escaped=${POSTGRES_DB//"/""}
db_escaped=${db_escaped//\'/''}

role_exists=$("${DC_CMD[@]}" exec -T db psql -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='${role_escaped}'" | tr -d '[:space:]')
if [ "$role_exists" != "1" ]; then
  echo "Creating role $POSTGRES_USER"
  "${DC_CMD[@]}" exec -T db psql -U postgres -c "CREATE ROLE \"${role_escaped}\" WITH LOGIN PASSWORD '${password_escaped}'"
else
  echo "Updating password for role $POSTGRES_USER"
  "${DC_CMD[@]}" exec -T db psql -U postgres -c "ALTER ROLE \"${role_escaped}\" WITH PASSWORD '${password_escaped}'"
fi

db_exists=$("${DC_CMD[@]}" exec -T db psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${db_escaped}'" | tr -d '[:space:]')
if [ "$db_exists" != "1" ]; then
  echo "Creating database $POSTGRES_DB owned by $POSTGRES_USER"
  "${DC_CMD[@]}" exec -T db psql -U postgres -c "CREATE DATABASE \"${db_escaped}\" OWNER \"${role_escaped}\""
else
  echo "Database $POSTGRES_DB already exists, ensuring owner"
  "${DC_CMD[@]}" exec -T db psql -U postgres -c "ALTER DATABASE \"${db_escaped}\" OWNER TO \"${role_escaped}\""
fi

echo "Granting privileges on database $POSTGRES_DB to $POSTGRES_USER"
"${DC_CMD[@]}" exec -T db psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE \"${db_escaped}\" TO \"${role_escaped}\""

echo "PostgreSQL role and database ensured successfully"


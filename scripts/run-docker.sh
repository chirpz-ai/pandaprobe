#!/bin/bash
set -e

# Script to securely run Docker containers

if [ $# -ne 1 ]; then
  echo "Usage: $0 <environment>"
  echo "Environments: development, staging, production"
  exit 1
fi

ENV=$1

# Validate environment
if [[ ! "$ENV" =~ ^(development|staging|production)$ ]]; then
  echo "Invalid environment. Must be one of: development, staging, production"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env.$ENV"

if [ -f "$ENV_FILE" ]; then
  echo "Loading environment variables from $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "Warning: $ENV_FILE not found. Relying on existing environment variables."
fi

cd "$PROJECT_ROOT"

if [ -f "$ENV_FILE" ]; then
  echo "Running docker compose with env file $ENV_FILE"
  APP_ENV=$ENV docker compose --env-file "$ENV_FILE" up -d --build db app
else
  APP_ENV=$ENV docker compose up -d --build db app
fi
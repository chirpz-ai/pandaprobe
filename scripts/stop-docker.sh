#!/bin/bash
set -e

# Script to stop and remove Docker containers

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

CONTAINER_NAME="fastapi-langgraph-$ENV"

echo "Stopping container for $ENV environment"

# Check if container exists
if [ ! "$(docker ps -a -q -f name=$CONTAINER_NAME)" ]; then
    echo "Container $CONTAINER_NAME does not exist. Nothing to do."
    exit 0
fi

# Stop and remove container
echo "Stopping container $CONTAINER_NAME..."
docker stop $CONTAINER_NAME >/dev/null 2>&1 || echo "Container was not running"

echo "Removing container $CONTAINER_NAME..."
docker rm $CONTAINER_NAME >/dev/null 2>&1

echo "Container $CONTAINER_NAME stopped and removed successfully"

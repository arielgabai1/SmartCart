#!/bin/bash
set -e

cd backend && .venv/bin/pytest tests
cd ..

PROJECT_NAME="smartcart-test"
COMPOSE_FILE="docker-compose.test.yml"

trap 'docker-compose -p $PROJECT_NAME -f $COMPOSE_FILE down --rmi local --remove-orphans' EXIT

docker-compose -p $PROJECT_NAME -f $COMPOSE_FILE up --build --abort-on-container-exit --exit-code-from test-runner > /dev/null 2>&1
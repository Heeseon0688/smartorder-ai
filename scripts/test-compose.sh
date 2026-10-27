#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null; then
  echo 'Docker Desktop (Apple Silicon) 설치·실행이 필요합니다.' >&2
  exit 1
fi
docker info >/dev/null
docker compose config --quiet
docker compose build
docker compose up -d --wait --wait-timeout 180
# PostgreSQL tests use a uniquely named temporary schema, not the app tables.
docker compose exec -T backend sh -c 'TEST_DATABASE_URL="$DATABASE_URL" python -m pytest -q'
# Explicit test fixture creation is inside a new temporary PostgreSQL schema.
# Browser E2E starts its own 8001/5174 servers and never resets the Compose DB.
echo 'Compose services healthy and PostgreSQL API tests passed.'
echo 'Browser integration: run scripts/test.sh (native) or CI PostgreSQL E2E.'

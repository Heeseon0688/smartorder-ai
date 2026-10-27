#!/bin/sh
set -eu
# Migrations run on the direct connection, before accepting requests. No seeding.
python -m app.manage migrate
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --no-access-log --log-level "${LOG_LEVEL:-info}"

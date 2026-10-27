#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PROJECT_DIR/.tools/node/bin:$PATH"
(cd "$PROJECT_DIR/backend" && .venv/bin/python -m pytest -q)
(cd "$PROJECT_DIR/frontend" && npm run build && npm run test:e2e)

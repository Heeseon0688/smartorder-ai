#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -d "$PROJECT_DIR/.tools/node/bin" ]; then
  export PATH="$PROJECT_DIR/.tools/node/bin:$PATH"
fi
if [ ! -x "$PROJECT_DIR/backend/.venv/bin/python" ] || [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
  echo '먼저 ./scripts/setup.sh 를 실행해 주세요.'
  exit 1
fi
(cd "$PROJECT_DIR/backend" && .venv/bin/python -m app.manage migrate)
backend_pid=''
frontend_pid=''
cleanup() {
  [ -z "$backend_pid" ] || kill "$backend_pid" 2>/dev/null || true
  [ -z "$frontend_pid" ] || kill "$frontend_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 0' INT TERM
(cd "$PROJECT_DIR/backend" && exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
backend_pid=$!
(cd "$PROJECT_DIR/frontend" && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173) &
frontend_pid=$!
echo 'SmartOrder AI: http://localhost:5173/admin (Ctrl+C로 종료)'
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do
  sleep 1
done
exit 1

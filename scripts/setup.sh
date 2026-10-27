#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
if [ -d "$PROJECT_DIR/.tools/node/bin" ]; then
  export PATH="$PROJECT_DIR/.tools/node/bin:$PATH"
fi
if ! command -v node >/dev/null || ! node -e 'if(Number(process.versions.node.split(".")[0])<20)process.exit(1)'; then
  echo 'Node.js 20.19+ 또는 22 LTS를 설치한 뒤 다시 실행해 주세요.'
  exit 1
fi
if [ ! -x backend/.venv/bin/python ]; then
  if [ -x .tools/bin/uv ] && [ -d .tools/python ]; then
    UV_PYTHON_INSTALL_DIR="$PROJECT_DIR/.tools/python" UV_CACHE_DIR="$PROJECT_DIR/.tools/uv-cache" .tools/bin/uv venv --python 3.12 backend/.venv
  else
    python_bin=''
    for candidate in python3.13 python3.12 python3.11 python3; do
      if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys;sys.exit(0 if sys.version_info >= (3,11) else 1)'; then
        python_bin="$candidate"
        break
      fi
    done
    if [ -z "$python_bin" ]; then echo 'Python 3.11+를 설치해 주세요.'; exit 1; fi
    "$python_bin" -m venv backend/.venv
  fi
fi
if [ -x .tools/bin/uv ]; then
  UV_CACHE_DIR="$PROJECT_DIR/.tools/uv-cache" .tools/bin/uv pip install --python backend/.venv/bin/python -r backend/requirements.lock.txt
else
  backend/.venv/bin/python -m pip install -r backend/requirements.lock.txt
fi
(cd frontend && npm ci)
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
fi
echo '준비 완료. ./scripts/dev.sh 로 시작하세요.'

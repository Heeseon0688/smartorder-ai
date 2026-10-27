#!/usr/bin/env python3
"""Create the first store administrator in the cloud (Neon) database.

Prompts for the Neon direct connection URL, admin email and password without
echoing secrets. Nothing is written to disk or shell history. Refuses to touch
an existing store or administrator.
"""
import getpass
import os
import subprocess
import sys
from pathlib import Path

backend = Path(__file__).resolve().parents[1] / 'backend'
python = backend / '.venv' / 'bin' / 'python'
if not python.exists():
    raise SystemExit('backend/.venv not found. Run ./scripts/setup.sh first.')

print('Neon 대시보드 → Connect → Connection pooling 끈 상태의 주소를 붙여 넣으세요 (화면에 표시되지 않습니다).')
url = getpass.getpass('Neon direct URL: ').strip().strip('"\'')
if not url.startswith(('postgres://', 'postgresql://', 'postgresql+psycopg://')) or 'sslmode=' not in url:
    raise SystemExit('PostgreSQL URL with sslmode=require is required. Nothing was changed.')
if '-pooler' in url:
    print('참고: pooler 주소입니다. 동작은 하지만 direct 주소를 권장합니다.')
with_menu = input('Smart Burger 메뉴 16개를 함께 넣을까요? (Y/n): ').strip().lower() != 'n'

env = {**os.environ, 'DATABASE_URL': url, 'MIGRATION_DATABASE_URL': '', 'APP_ENV': 'development', 'OPENAI_API_KEY': ''}
command = [str(python), '-m', 'app.manage', 'bootstrap'] + (['--with-menu'] if with_menu else [])
sys.exit(subprocess.run(command, cwd=backend, env=env).returncode)

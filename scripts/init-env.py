#!/usr/bin/env python3
"""Create a private local Docker env once. Never print credentials or replace files."""
import os
import secrets
from pathlib import Path
path = Path(__file__).resolve().parents[1] / '.env'
try:
    descriptor = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit('.env already exists; left unchanged. Compare it with .env.example.')
with os.fdopen(descriptor, 'w') as output:
    output.write('POSTGRES_PASSWORD='+secrets.token_hex(24)+'\n')
    output.write('FRONTEND_URL=http://localhost:5173\nFRONTEND_BIND=127.0.0.1\n')
    output.write('ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]\n')
    output.write('ENABLE_DEMO_LINK=true\nOPENAI_API_KEY=\nOPENAI_MODEL=gpt-4.1-mini\n')
print('Created private .env. Run: docker compose up --build')

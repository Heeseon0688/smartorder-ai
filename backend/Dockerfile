# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
RUN python -m venv /opt/venv
COPY requirements.lock.txt ./
RUN pip install --disable-pip-version-check -r requirements.lock.txt
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./
RUN chown app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/ready', timeout=4)"
# Migrations run on the direct connection before accepting requests. No seeding.
CMD ["sh", "-c", "python -m app.manage migrate && exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 1 --no-access-log --log-level \"${LOG_LEVEL:-info}\""]

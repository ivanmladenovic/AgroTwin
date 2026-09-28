#!/bin/sh
set -eu

echo "Running database migrations..."
alembic upgrade head

if [ "${RUN_SEED:-false}" = "true" ]; then
  echo "Seeding demo data (RUN_SEED=true)..."
  python scripts/seed.py
fi

# Restore Agriser PDF binaries when local storage was wiped (common on Render free).
if [ -d "/app/Prirucnici" ] || [ -d "../Prirucnici" ]; then
  echo "Ensuring knowledge manuals are present in storage..."
  python scripts/ingest_knowledge.py || echo "Knowledge ingest skipped (non-fatal)."
fi

PORT="${PORT:-8000}"
echo "Starting AgroTwin API on port ${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"

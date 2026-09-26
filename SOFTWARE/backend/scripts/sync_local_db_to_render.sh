#!/usr/bin/env bash
# Restore local AgroTwin database dump onto Render Postgres.
#
# Usage:
#   1. In Render → agrotwin-db → Info → copy "External Database URL"
#   2. export RENDER_DATABASE_URL='postgresql://...'
#   3. ./scripts/sync_local_db_to_render.sh
#
# Optional:
#   DUMP_FILE=var/backups/agrotwin_local_YYYYMMDD.dump ./scripts/sync_local_db_to_render.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "${RENDER_DATABASE_URL:-}" ]]; then
  echo "Set RENDER_DATABASE_URL to the Render External Database URL first."
  echo "Dashboard → agrotwin-db → Info → Connections → External Database URL"
  exit 1
fi

DUMP_FILE="${DUMP_FILE:-$(ls -1t var/backups/agrotwin_local_*.dump 2>/dev/null | head -1 || true)}"
if [[ -z "$DUMP_FILE" || ! -f "$DUMP_FILE" ]]; then
  echo "No dump found. Creating one from local Docker Postgres..."
  mkdir -p var/backups
  DUMP_FILE="var/backups/agrotwin_local_$(date +%Y%m%d_%H%M%S).dump"
  PGPASSWORD="${POSTGRES_PASSWORD:-agrotwin}" pg_dump \
    -h "${POSTGRES_HOST:-localhost}" \
    -p "${POSTGRES_PORT:-5433}" \
    -U "${POSTGRES_USER:-agrotwin}" \
    -d "${POSTGRES_DB:-agrotwin}" \
    -Fc --no-owner --no-acl \
    -f "$DUMP_FILE"
fi

echo "Using dump: $DUMP_FILE"
echo "Target: Render Postgres (external URL)"

# Ensure SSL for Render external connections
TARGET_URL="$RENDER_DATABASE_URL"
if [[ "$TARGET_URL" != *"sslmode="* ]]; then
  if [[ "$TARGET_URL" == *"?"* ]]; then
    TARGET_URL="${TARGET_URL}&sslmode=require"
  else
    TARGET_URL="${TARGET_URL}?sslmode=require"
  fi
fi

echo "Dropping existing public schema objects on Render (clean restore)..."
psql "$TARGET_URL" -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO CURRENT_USER;
GRANT ALL ON SCHEMA public TO public;
SQL

echo "Restoring..."
pg_restore \
  --dbname="$TARGET_URL" \
  --verbose \
  --no-owner \
  --no-acl \
  --exit-on-error \
  "$DUMP_FILE"

echo "Done. Verify with:"
echo "  psql \"\$RENDER_DATABASE_URL?sslmode=require\" -c \"SELECT name FROM parcels;\""
echo "Then open https://agrotwin-web.onrender.com and log in with your local admin credentials."

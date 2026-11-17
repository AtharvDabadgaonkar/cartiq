#!/usr/bin/env bash
# Point a deployed database at this schema and load the seed.
#
#   DATABASE_URL="<pooled>" DIRECT_URL="<direct>" ./scripts/setup_remote_db.sh
#
# Both are needed: Prisma migrations cannot run through a transaction pooler,
# so DIRECT_URL is used for the migration and DATABASE_URL for everything else.
# Credentials are read from the environment and never echoed.
set -euo pipefail

: "${DATABASE_URL:?set DATABASE_URL to the pooled connection string}"
: "${DIRECT_URL:?set DIRECT_URL to the direct connection string}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/apps/api/.venv/bin/python"

# Show the host only, so a password never reaches the terminal or a log.
host=$(printf '%s' "$DATABASE_URL" | sed -E 's|.*@([^/?]+).*|\1|')
echo "target host: $host"

echo "==> applying migrations"
pnpm --filter @cartiq/web exec prisma migrate deploy

echo "==> building SQL models"
"$PY" "$ROOT/scripts/build_models.py"

echo "==> loading the committed seed"
"$PY" "$ROOT/scripts/seed.py"

echo
echo "done. Verify with:"
echo "  psql \"\$DATABASE_URL\" -c 'SELECT data_source, count(*) FROM events GROUP BY 1;'"

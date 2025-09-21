#!/usr/bin/env bash
set -Eeuo pipefail
PG_URL="${1:-${SQLALCHEMY_URL:-}}"
if [[ -z "$PG_URL" ]]; then
  echo "Usage: $0 'postgresql+psycopg2://user:pass@host:5432/dbname'"; exit 2
fi
# shellcheck disable=SC1091
source .venv_clean/bin/activate
export SQLALCHEMY_URL="$PG_URL"
echo "[PG] alembic upgrade head -> $PG_URL"
alembic upgrade head
echo "[PG] done."

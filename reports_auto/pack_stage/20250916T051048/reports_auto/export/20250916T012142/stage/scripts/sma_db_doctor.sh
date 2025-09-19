#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1090
source .sma_tools/env_guard.sh

DB="${SMA_DB_PATH:-db/sma.sqlite}"
echo "[INFO] DB: $DB"

echo "[SCHEMA] mails:"
sqlite3 "$DB" 'PRAGMA table_info(mails);'
echo
echo "[SCHEMA] intent_preds:"
sqlite3 "$DB" 'PRAGMA table_info(intent_preds);'
echo
echo "[SCHEMA] actions:"
sqlite3 "$DB" 'PRAGMA table_info(actions);'
echo
echo "[INDEX] mails indexes:"
sqlite3 "$DB" 'PRAGMA index_list(mails);'
echo
echo "[ACTION] running migrate/repair..."
python scripts/sma_db_migrate.py
echo "[DONE] see reports_auto/status for the migration report."

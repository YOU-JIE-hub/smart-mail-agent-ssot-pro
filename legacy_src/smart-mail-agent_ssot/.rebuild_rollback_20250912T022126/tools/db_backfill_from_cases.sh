#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$PWD}"
DB="${DB:-db/sma.sqlite}"
RUN_DIR="${RUN_DIR:-$(ls -td reports_auto/e2e_mail/* | head -n1)}"
[ -f "$DB" ] || { echo "[FATAL] not found DB: $DB"; exit 2; }
[ -f "$RUN_DIR/cases.jsonl" ] || { echo "[FATAL] not found cases: $RUN_DIR/cases.jsonl"; exit 3; }

# 準備暫存 CSV（id, subject, from_addr, to_addr, received_at, raw_path）
TMP="$ROOT/reports_auto/logs/cases_for_mails.csv"
jq -r '[.id, (.subject//""), (.from//""), (.to//""), (.received_at//""), (.raw_path//"")] | @csv' \
   "$RUN_DIR/cases.jsonl" > "$TMP"

# 建立 mails 表（若尚未存在；欄位名依你現有 schema 可調）
sqlite3 "$DB" <<'SQL'
CREATE TABLE IF NOT EXISTS mails (
  id TEXT PRIMARY KEY,
  subject TEXT,
  from_addr TEXT,
  to_addr TEXT,
  received_at TEXT,
  raw_path TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
SQL

# 以 INSERT OR IGNORE 匯入，避免重覆
sqlite3 "$DB" <<SQL
.mode csv
.separator ,
.import --skip 0 "$TMP" mails
SQL

echo "[OK] backfill completed → $DB ; source=$RUN_DIR"

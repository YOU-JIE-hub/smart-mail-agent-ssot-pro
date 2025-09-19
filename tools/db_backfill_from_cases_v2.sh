#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$PWD}"
DB="${DB:-db/sma.sqlite}"
RUN_DIR="${RUN_DIR:-$(ls -td reports_auto/e2e_mail/* | head -n1)}"
[ -f "$DB" ] || { echo "[FATAL] not found DB: $DB"; exit 2; }
[ -f "$RUN_DIR/cases.jsonl" ] || { echo "[FATAL] not found cases: $RUN_DIR/cases.jsonl"; exit 3; }

TMP="$ROOT/reports_auto/logs/cases_for_mails.csv"
mkdir -p "$(dirname "$TMP")"

# 1) 將 cases.jsonl 萃成 6 欄 CSV（id, subject, from, to, received_at, raw_path）
jq -r '[.id, (.subject//""), (.from//""), (.to//""), (.received_at//""), (.raw_path//"")] | @csv' \
   "$RUN_DIR/cases.jsonl" > "$TMP"

# 2) 用暫存表承接 CSV，避免直接撞唯一鍵
sqlite3 "$DB" <<SQL
PRAGMA foreign_keys=OFF;
DROP TABLE IF EXISTS __tmp_cases__;
CREATE TABLE __tmp_cases__(
  id TEXT PRIMARY KEY,
  subject TEXT,
  from_addr TEXT,
  to_addr TEXT,
  received_at TEXT,
  raw_path TEXT
);
.mode csv
.import "$TMP" __tmp_cases__
SQL

# 3) 自動偵測 mails 結構；如無則用 case_id 風格建立
HAS_MAILS="$(sqlite3 "$DB" "SELECT name FROM sqlite_master WHERE type='table' AND name='mails';")"
if [ -z "$HAS_MAILS" ]; then
  sqlite3 "$DB" <<'SQL'
CREATE TABLE mails (
  case_id TEXT PRIMARY KEY,
  subject TEXT,
  from_addr TEXT,
  to_addr TEXT,
  received_at TEXT,
  raw_path TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
SQL
fi

HAS_ID_COL="$(sqlite3 "$DB" "PRAGMA table_info(mails);" | awk -F'|' '$2=="id"{print 1; exit}')"
HAS_CASE_ID_COL="$(sqlite3 "$DB" "PRAGMA table_info(mails);" | awk -F'|' '$2=="case_id"{print 1; exit}')"

# 4) 依偵測結果做合併（忽略已存在主鍵）
if [ "$HAS_ID_COL" = "1" ]; then
  sqlite3 "$DB" <<'SQL'
INSERT OR IGNORE INTO mails (id, subject, from_addr, to_addr, received_at, raw_path)
SELECT id, subject, from_addr, to_addr, received_at, raw_path
FROM __tmp_cases__;
SQL
elif [ "$HAS_CASE_ID_COL" = "1" ]; then
  sqlite3 "$DB" <<'SQL'
INSERT OR IGNORE INTO mails (case_id, subject, from_addr, to_addr, received_at, raw_path)
SELECT id, subject, from_addr, to_addr, received_at, raw_path
FROM __tmp_cases__;
SQL
else
  echo "[FATAL] mails 表沒有 id 也沒有 case_id 欄，請檢查 schema"
  exit 9
fi

# 5) 建立相容視圖（以後查詢可統一 SELECT id ... FROM mails_compat）
if [ "$HAS_CASE_ID_COL" = "1" ]; then
  sqlite3 "$DB" "CREATE VIEW IF NOT EXISTS mails_compat AS SELECT case_id AS id, subject, from_addr, to_addr, received_at, raw_path, created_at FROM mails;"
else
  sqlite3 "$DB" "CREATE VIEW IF NOT EXISTS mails_compat AS SELECT id, subject, from_addr, to_addr, received_at, raw_path, created_at FROM mails;"
fi

# 6) 清理暫存表並列出摘要
CNT_ALL="$(sqlite3 "$DB" 'SELECT COUNT(*) FROM mails;')"
CNT_NEW="$(sqlite3 "$DB" 'SELECT COUNT(*) FROM __tmp_cases__ WHERE id IN (SELECT (CASE WHEN (SELECT COUNT(*) FROM pragma_table_info("mails") WHERE name="case_id")>0 THEN case_id ELSE id END) FROM mails);')"
sqlite3 "$DB" 'DROP TABLE IF EXISTS __tmp_cases__;'

echo "[OK] backfill done → $DB"
echo " - mails total: $CNT_ALL"

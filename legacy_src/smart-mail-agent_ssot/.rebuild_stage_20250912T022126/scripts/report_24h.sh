#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$PWD}"
cd "$ROOT"
DB="reports_auto/audit.sqlite3"
[[ -f "$DB" ]] || { echo "[FATAL] missing DB: $DB" >&2; exit 97; }

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/status/REPORT_24H_${TS}.md"

{
  echo "# REPORT_24H @ ${TS}"
  echo
  echo "## actions 直方圖"
  sqlite3 "$DB" "SELECT status, COUNT(*) FROM actions GROUP BY status;" | sed 's/^/- /'
  echo
  echo "## intents 分布（24h）"
  sqlite3 "$DB" "SELECT intent, COUNT(*) FROM actions WHERE ts >= strftime('%s','now','-1 day') GROUP BY intent ORDER BY 2 DESC;" | sed 's/^/- /'
  echo
  echo "## 最近 errors（最多 10 筆）"
  sqlite3 "$DB" "SELECT datetime(ts,'unixepoch') AS ts_human, stage, mail_id, message FROM errors ORDER BY ts DESC LIMIT 10;" \
    | sed 's/^/- /'
  echo
  echo "## actions_history 近 20 筆"
  sqlite3 "$DB" "SELECT datetime(ts,'unixepoch'), idempotency_key, old_status, new_status FROM actions_history ORDER BY ts DESC LIMIT 20;" \
    | sed 's/^/- /'
  echo
  if sqlite3 "$DB" "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_tickets';" | grep -q 1; then
    echo "## v_tickets / v_answers 計數"
    echo "- tickets: $(sqlite3 "$DB" "SELECT COUNT(*) FROM v_tickets;")"
    echo "- answers: $(sqlite3 "$DB" "SELECT COUNT(*) FROM v_answers;")"
    echo
  fi
} > "$OUT"

echo "$OUT"

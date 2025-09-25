#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$PWD}"
cd "$ROOT"
DB="reports_auto/audit.sqlite3"

echo "=== [OPS QUICKCHECK] ==="
[[ -f "$DB" ]] || { echo "[FATAL] missing DB: $DB"; exit 97; }

echo "[ACTIONS HIST]"
sqlite3 "$DB" "SELECT status, COUNT(*) FROM actions GROUP BY status;"

echo "[ERRORS TOP5]"
sqlite3 "$DB" "SELECT datetime(ts,'unixepoch'), stage, mail_id, message FROM errors ORDER BY ts DESC LIMIT 5;"

echo "[VIEWS CHECK]"
sqlite3 "$DB" "SELECT 'tickets', (SELECT COUNT(*) FROM v_tickets), 'answers', (SELECT COUNT(*) FROM v_answers);" 2>/dev/null || echo "[WARN] views not present (ok if phase12 didn't create)"

echo "[TRIGGER CHECK]"
sqlite3 "$DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name='trg_actions_status';"

ERR=$(sqlite3 "$DB" "SELECT COUNT(*) FROM actions WHERE status='error';")
QUE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM actions WHERE status='queued';")
if [[ "$ERR" -eq 0 && "$QUE" -eq 0 ]]; then
  echo "[GATE] CLEAN ✅ (error=0, queued=0)"
  exit 0
else
  echo "[GATE] NOT CLEAN ❌ (error=$ERR, queued=$QUE)"
  exit 90
fi

#!/usr/bin/env bash
set -Euo pipefail
ROOT="${1:-${SMA_ROOT:-$PWD}}"
cd "$ROOT" 2>/dev/null || { echo "[FATAL] bad ROOT=$ROOT"; exit 96; }

echo "=== [ENV] ==="; echo "ROOT=$(pwd)"; echo
pick(){ ls -1t "reports_auto/logs/$1" 2>/dev/null | head -n1 || true; }

echo "=== [CRASH] 最新 ==="
cr="$(pick 'CRASH_*.log')"
if [[ -n "$cr" ]]; then echo "--- $cr (tail -n 120) ---"; tail -n 120 "$cr"; else echo "[OK] 無 CRASH_*.log"; fi
echo

echo "=== [PHASE9* 日誌] 最新 ==="
ph="$(pick 'PHASE9*.log')"
if [[ -n "$ph" ]]; then echo "--- $ph (tail -n 200) ---"; tail -n 200 "$ph"; else echo "[WARN] 找不到 PHASE9* 日誌"; fi
echo

echo "=== [DB 快照]（若有 sqlite3 與 DB） ==="
if [[ -f reports_auto/audit.sqlite3 && "$(command -v sqlite3 || true)" != "" ]]; then
sqlite3 reports_auto/audit.sqlite3 <<'SQL'
.headers on
.mode column
SELECT datetime(ts,'unixepoch') AS ts, stage, mail_id, type, message
FROM errors ORDER BY ts DESC LIMIT 10;
SELECT status, COUNT(*) AS cnt FROM actions GROUP BY status ORDER BY status;
SELECT datetime(ts,'unixepoch') AS ts, idempotency_key, old_status, new_status
FROM actions_history ORDER BY ts DESC LIMIT 10;
SQL
else
  [[ ! -f reports_auto/audit.sqlite3 ]] && echo "[WARN] DB 不在 reports_auto/audit.sqlite3"
  [[ "$(command -v sqlite3 || true)" == "" ]] && echo "[WARN] 未安裝 sqlite3，略過 DB 查詢"
fi
echo

echo "=== [TAIL] pipeline.ndjson ==="
pn="reports_auto/e2e_mail/pipeline.ndjson"
[[ -f "$pn" ]] && tail -n 60 "$pn" || echo "[HINT] $pn 不存在"

#!/usr/bin/env bash
set -Eeuo pipefail
TS="$(date +%Y%m%dT%H%M%S)"
ROOT="$HOME/projects/smart-mail-agent_ssot"
OUT="$ROOT/reports_auto/crash_bundles/${TS}"
LOG="$OUT/error_${TS}.log"
mkdir -p "$OUT"

# 把所有輸出同步寫入錯誤檔
exec > >(tee -a "$LOG") 2>&1
trap 'echo "[ERR] line:$LINENO cmd:${BASH_COMMAND}" >> "$LOG"' ERR

redact(){ sed -E 's/(OPENAI_API_KEY|SMTP_PASS|SMA_SMTP_PASS)=([^[:space:]]+)/\1=***REDACTED***/g'; }

echo "[ENV]" && env | redact | sort > "$OUT/env_${TS}.txt"

echo "[STEP] pytest -q tests/test_spam_orchestrator.py"
pytest -q tests/test_spam_orchestrator.py || true

echo "[STEP] python -m smart_mail_agent.cli.e2e --eml-dir tests/_data/eml --out-root . --db-path db/sma.sqlite --ndjson ."
python -m smart_mail_agent.cli.e2e --eml-dir tests/_data/eml --out-root . --db-path db/sma.sqlite --ndjson . || true

# 收集輔助資訊（若有則寫入）
{ tail -n 200 "$ROOT"/reports_auto/events/*.ndjson 2>/dev/null || true; } > "$OUT/events_tail_${TS}.ndjson"
{ find "$ROOT"/reports_auto -type f \( -name 'error_*.log' -o -name 'send_*.log' \) 2>/dev/null || true; } > "$OUT/found_logs_${TS}.txt"
sqlite3 db/sma.sqlite 'pragma integrity_check;' > "$OUT/sqlite_integrity_${TS}.txt" 2>&1 || true
{ echo "[TREE]"; find "$ROOT/reports_auto/e2e_mail" -maxdepth 3 -type d 2>/dev/null || true; } > "$OUT/tree_${TS}.txt"

echo "BUNDLE_DIR=$OUT" | tee "$OUT/where.txt"

# 自動開資料夾（WSL/ Linux / mac）
if grep -qi microsoft /proc/version 2>/dev/null; then
  explorer.exe "$(wslpath -w "$OUT")" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$OUT" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "$OUT" >/dev/null 2>&1 || true
fi

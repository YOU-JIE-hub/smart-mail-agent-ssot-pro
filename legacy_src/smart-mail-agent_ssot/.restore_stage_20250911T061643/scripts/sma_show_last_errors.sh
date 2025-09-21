#!/usr/bin/env bash
set -Eeuo pipefail
LOG="reports_auto/logs/last.log"
if [[ ! -f "$LOG" ]]; then
  CAND="$(ls -1t reports_auto/logs/run_*.log 2>/dev/null | head -n1 || true)"
  [[ -n "$CAND" ]] && LOG="$CAND" || { echo "[INFO] 尚無日誌。先跑：scripts/sma_e2e_oneclick_logged.sh"; exit 0; }
fi
grep -nE "ERROR|WARN|Traceback|Exception|failed" "$LOG" || echo "[OK] 無錯誤關鍵字"
echo -e "\n[PATH] $LOG"

#!/usr/bin/env bash
set -Eeuo pipefail
LOG="reports_auto/logs/last.log"
if [[ ! -f "$LOG" ]]; then
  CAND="$(ls -1t reports_auto/logs/run_*.log 2>/dev/null | head -n1 || true)"
  if [[ -n "$CAND" ]]; then
    LOG="$CAND"
  else
    echo "[INFO] 尚無日誌。先跑：scripts/sma_e2e_oneclick_logged.sh"
    exit 0
  fi
fi
${PAGER:-less} "$LOG"

#!/usr/bin/env bash
set -Eeuo pipefail
source .sma_tools/env_guard.sh
LOG_DIR="reports_auto/logs"
mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%dT%H%M%S)"
LOG="$LOG_DIR/run_${TS}.log"
{
  echo "[BEGIN] started at $(date +%Y-%m-%dT%H:%M:%S%z)"
  echo "[INFO] log file: $LOG"
  echo "[INFO] cwd: $(pwd)"
  echo "[INFO] python: $(command -v python) ($(python -V))"
  echo "[INFO] SMA_DB_PATH=${SMA_DB_PATH:-db/sma.sqlite}"

  echo -e "\n========== RUN: scripts/sma_fix_artifacts.sh =========="
  bash scripts/sma_fix_artifacts.sh
  echo "---------- DONE: rc=$? ----------"

  echo -e "\n========== RUN: python scripts/sma_db_migrate.py =========="
  python scripts/sma_db_migrate.py
  echo "---------- DONE: rc=$? ----------"

  echo -e "\n========== RUN: scripts/sma_project_audit.sh =========="
  bash scripts/sma_project_audit.sh
  echo "---------- DONE: rc=$? ----------"

  echo -e "\n========== RUN: scripts/sma_e2e_mail.sh data/demo_eml =========="
  bash scripts/sma_e2e_mail.sh data/demo_eml
  RC=$?
  echo "---------- DONE: rc=$RC ----------"

  # 更新最後日誌
  ln -sfn "$LOG" "$LOG_DIR/last.log"

  # 只挑選實際 run 目錄，忽略 /LATEST
  LAST_RUN="$(ls -1dt reports_auto/e2e_mail/* 2>/dev/null | grep -v '/LATEST$' | head -n1 || true)"
  if [[ -n "${LAST_RUN:-}" && -d "$LAST_RUN" ]]; then
    ln -sfn "$LAST_RUN" "reports_auto/e2e_mail/LATEST"
  fi

  echo "[END] finished at $(date +%Y-%m-%dT%H:%M:%S%z)"
} | tee "$LOG"

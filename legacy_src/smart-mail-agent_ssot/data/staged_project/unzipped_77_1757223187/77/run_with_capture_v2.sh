#!/usr/bin/env bash
set -Eeuo pipefail; set -o errtrace; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$ROOT" || { echo "[FATAL] repo not found: $ROOT"; exit 96; }
[ -f ".venv/bin/activate" ] && source ".venv/bin/activate" 2>/dev/null || true
mkdir -p .sma_logs; chmod u+rwX .sma_logs || true

TAG="job"; if [ "${1:-}" = "--tag" ]; then TAG="$2"; shift 2; fi
TS="$(date +%Y-%m-%d_%H%M%S)"
LOG=".sma_logs/${TAG}_${TS}.log"
ERR=".sma_logs/${TAG}_${TS}.err"
CMD=("$@"); if [ ${#CMD[@]} -eq 0 ]; then echo "[FATAL] no command"; exit 97; fi

# 以純重導方式執行，確保任何早期錯誤都進檔
{
  echo "[INFO] ROOT=$ROOT"
  echo "[INFO] CMD=${CMD[*]}"
  echo "[INFO] TS=$TS"
  echo "----- RUN STDOUT/STDERR BELOW -----"
  "${CMD[@]}"
} >"$LOG" 2>"$ERR"
RC=$?

ln -sfn "$(basename "$LOG")" .sma_logs/latest.log
ln -sfn "$(basename "$ERR")" .sma_logs/latest.err

if [ $RC -ne 0 ]; then
  SUMMARY=".sma_logs/latest_error.txt"
  {
    echo "[FAIL] rc=$RC  cmd: ${CMD[*]}"
    echo "[LOG] $LOG"
    echo "[ERR] $ERR"
    echo "----- tail -n 120 of ERR -----"
    tail -n 120 "$ERR" 2>/dev/null || true
    echo "----- tail -n 80 of LOG -----"
    tail -n 80 "$LOG" 2>/dev/null || true
  } > "$SUMMARY"
  ln -sfn "$(basename "$SUMMARY")" .sma_logs/latest_error.link
  sed -n '1,200p' "$SUMMARY"
  exit $RC
else
  echo "[OK] rc=0  tag=$TAG"
  echo "[LOG] $LOG"
fi

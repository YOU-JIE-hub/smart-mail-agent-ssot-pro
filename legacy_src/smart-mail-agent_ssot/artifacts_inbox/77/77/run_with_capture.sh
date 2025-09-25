#!/usr/bin/env bash
set -Eeuo pipefail
set -o errtrace
umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$ROOT" || { echo "[FATAL] repo not found: $ROOT"; exit 96; }
[ -f ".venv/bin/activate" ] && source ".venv/bin/activate" 2>/dev/null || true

mkdir -p .sma_logs
TS="$(date +%Y-%m-%d_%H%M%S)"
LOG=".sma_logs/capture_${TS}.log"
CMD=("$@")
if [ ${#CMD[@]} -eq 0 ]; then
  CMD=(sma_tools/panic_doctor.sh)  # 沒給參數就預設跑 panic_doctor
fi

echo "[INFO] ROOT=$ROOT"
echo "[INFO] CMD=${CMD[*]}"
echo "[INFO] LOG=$LOG"

# 執行並同時寫檔
set +e
"${CMD[@]}" |& tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

ln -sfn "$(basename "$LOG")" .sma_logs/latest.log

if [ $RC -ne 0 ]; then
  ERR=".sma_logs/latest_error.txt"
  {
    echo "[FAIL] cmd: ${CMD[*]}  rc=$RC"
    echo "[LOG] $LOG"
    echo "----- tail -n 200 of LOG -----"
    tail -n 200 "$LOG" 2>/dev/null || true
    echo "----- grep FAIL lines (last 10) -----"
    grep -n "FAIL" "$LOG" 2>/dev/null | tail -n 10 || true
  } > "$ERR"
  ln -sfn "$(basename "$ERR")" .sma_logs/latest_error.link
  echo "[SAVED] $ERR"
  # 直接打開（列印前 200 行；要看完整可自行用 less）
  sed -n '1,200p' "$ERR"
  exit $RC
else
  echo "[OK] command succeeded; log: $LOG"
fi

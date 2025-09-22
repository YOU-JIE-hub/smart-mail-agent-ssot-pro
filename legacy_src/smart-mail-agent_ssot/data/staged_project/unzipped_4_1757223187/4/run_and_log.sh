#!/usr/bin/env bash
set -Eeuo pipefail; set -o errtrace; umask 022
trap 'rc=$?; echo "[TRAP] rc=$rc last=${BASH_COMMAND}" >>"$ERR"; exit $rc' ERR
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$ROOT" || { echo "[FATAL] repo not found: $ROOT"; exit 96; }
[ -f ".venv/bin/activate" ] && source ".venv/bin/activate" 2>/dev/null || true
mkdir -p .sma_logs
TAG="${1:?tag required}"; shift
TS="$(date +%Y-%m-%d_%H%M%S)"
LOG=".sma_logs/${TAG}_${TS}.log"
ERR=".sma_logs/${TAG}_${TS}.err"
TRACE=".sma_logs/${TAG}_${TS}.trace"
exec 19> "$TRACE"; export BASH_XTRACEFD=19; set -x
{
  echo "[INFO] ROOT=$ROOT"
  echo "[INFO] TS=$TS"
  echo "[INFO] CMD=$*"
  echo "----- RUN START -----"
  "$@"
  echo "----- RUN END -----"
} >"$LOG" 2>"$ERR"; rc=$?
ln -sfn "$(basename "$LOG")"   ".sma_logs/${TAG}.log"
ln -sfn "$(basename "$ERR")"   ".sma_logs/${TAG}.err"
ln -sfn "$(basename "$TRACE")" ".sma_logs/${TAG}.trace"
if [ $rc -ne 0 ]; then
  SUMMARY=".sma_logs/latest_error.txt"
  {
    echo "[FAIL] rc=$rc  tag=$TAG"
    echo "[LOG]  $LOG"
    echo "[ERR]  $ERR"
    echo "[TRACE] $TRACE"
    echo "----- tail ERR (120) -----";   tail -n 120 "$ERR"   2>/dev/null || true
    echo "----- tail LOG (80) ------";   tail -n 80  "$LOG"   2>/dev/null || true
    echo "----- tail TRACE (60) ----";   tail -n 60  "$TRACE" 2>/dev/null || true
  } > "$SUMMARY"
  sed -n '1,200p' "$SUMMARY"
  exit $rc
else
  echo "[OK] rc=0  tag=$TAG"
  echo "[LOG] $LOG"
fi

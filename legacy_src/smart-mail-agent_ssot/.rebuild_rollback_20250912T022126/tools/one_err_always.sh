#!/usr/bin/env bash
set -o pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="$ROOT/reports_auto/logs"; mkdir -p "$LOGDIR"
TAG="${1:-run}"; shift || true
CMD=( "$@" ); [ ${#CMD[@]} -gt 0 ] || CMD=(true)
TS="$(date +%Y%m%dT%H%M%S)"; SAFE="$(printf '%s' "$TAG" | sed 's/[ \/|:&><]/_/g' | tr -cd 'A-Za-z0-9_.-')"
LOG="$LOGDIR/${SAFE}_${TS}.log"; COMB="$LOGDIR/${SAFE}_${TS}.combined.tmp"; ERR="$LOGDIR/${SAFE}_${TS}.err"
{
  echo "========== ONE-ERR =========="; echo "Tag: $SAFE"; echo "When: $(date -Iseconds)"
  echo "Command: ${CMD[*]}"; echo "Workdir: $ROOT"; echo "System: $(uname -a)"; echo "Python: $(python -V 2>&1 || true)"
  echo "--------------------------------"
} >"$ERR"
# 收集輸出
stdbuf -oL -eL "${CMD[@]}" 2>&1 | tee "$COMB" | tee -a "$LOG" >/dev/null
EC=${PIPESTATUS[0]}
if [ $EC -ne 0 ]; then
  { echo; echo "---- STDOUT+STDERR (combined) ----"; cat "$COMB"; echo; echo "========== END ONE-ERR =========="; } >>"$ERR"
  rm -f "$COMB"
  if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$LOGDIR")" || true; else (xdg-open "$LOGDIR" >/dev/null 2>&1 || true); fi
  echo "[ONE-ERR] wrote: $ERR"; exit $EC
fi
rm -f "$ERR" "$COMB"; echo "[OK] logs: $LOG"; exit 0

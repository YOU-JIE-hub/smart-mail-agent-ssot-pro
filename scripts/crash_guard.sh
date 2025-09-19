#!/usr/bin/env bash
# 用法： scripts/crash_guard.sh --cmd 'python -m tools.api_server'
set -Eeuo pipefail -o errtrace
TS="$(date +%Y%m%dT%H%M%S)"
ROOT="${ROOT:-$PWD}"
OUT="reports_auto/ERR/CRASH_${TS}"
mkdir -p "$OUT"
RUN_OUT="$OUT/run.out"; RUN_ERR="$OUT/run.err"
: >"$RUN_OUT"; : >"$RUN_ERR"

_open_folder() {
  if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$1")" || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$1" || true
  fi
}

_summary() {
  local rc="$1" msg="$2"
  {
    echo "When : $TS"
    echo "CWD  : $ROOT"
    echo "RC   : $rc"
    echo "Cmd  : $CMD"
    echo "Msg  : $msg"
    echo
    echo "== tail run.out =="; tail -n 120 "$RUN_OUT" 2>/dev/null || true
    echo; echo "== tail run.err =="; tail -n 120 "$RUN_ERR" 2>/dev/null || true
    echo; echo "== ss -ltnp =="; ss -ltnp 2>&1 | tail -n 120 || true
    echo; echo "== ps -ef | python =="; ps -ef | grep -E 'python|api_server' | grep -v grep || true
  } > "$OUT/CRASH_SUMMARY.txt"
  echo "$OUT" > reports_auto/ERR/LATEST_CRASH
  echo "[CRASH] $OUT/CRASH_SUMMARY.txt"
  _open_folder "$OUT"
}

trap 'RC=$?; _summary "$RC" "trap ERR: $BASH_COMMAND (line ${BASH_LINENO[0]:-NA})"; exit "$RC"' ERR
trap 'RC=$?; [ "$RC" -eq 0 ] || _summary "$RC" "trap EXIT non-zero" ' EXIT

CMD=""
# 解析參數
while [ $# -gt 0 ]; do
  case "$1" in
    --cmd) shift; CMD="$1";;
    *) echo "[WARN] unknown arg: $1";;
  esac
  shift || true
done
[ -n "$CMD" ] || { echo "[FATAL] no --cmd given" | tee -a "$RUN_ERR"; exit 97; }

echo "[RUN] $CMD" | tee -a "$RUN_OUT"
# 確保 python 不緩衝 & 開啟 faulthandler
export PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
# 用 stdbuf 讓輸出行緩衝，立刻落檔
stdbuf -oL -eL bash -lc "$CMD" >>"$RUN_OUT" 2>>"$RUN_ERR"
# 能走到這代表沒錯（trap EXIT 會看到 RC=0 就不產 CRASH）
echo "[OK] finished: $CMD" | tee -a "$RUN_OUT"

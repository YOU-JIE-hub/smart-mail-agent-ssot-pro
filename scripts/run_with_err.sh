#!/usr/bin/env bash
# run_with_err.sh — 包裹任何指令；把錯誤與路徑固定鏡射到 reports_auto/ERR
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
RUN="reports_auto/wrap/${TS}"
ERR_DIR="$ROOT/reports_auto/ERR"
mkdir -p "$RUN" "$ERR_DIR"

RUNLOG="$RUN/run.log"
XTRACE="$RUN/xtrace.log"
ERRFILE="$RUN/pack.err"
WHERE="$ERR_DIR/where.txt"

print_paths(){ cat <<EOF
[PATHS]
  RUN_DIR=$(cd "$RUN" && pwd)
  RUNLOG=$(cd "$RUN" && pwd)/run.log
  XTRACE=$(cd "$RUN" && pwd)/xtrace.log
  ERR   =$ERR_DIR/pack.err
  WHERE =$ERR_DIR/where.txt
EOF
}
mirror(){ cp -f "$RUNLOG" "$ERR_DIR/run.log" 2>/dev/null || true
          cp -f "$XTRACE" "$ERR_DIR/xtrace.log" 2>/dev/null || true
          cp -f "$ERRFILE" "$ERR_DIR/pack.err" 2>/dev/null || true
          printf "RUN_DIR=%s\n" "$(cd "$RUN" && pwd)" > "$WHERE"; }

on_sig(){ sig="$1"; code="$2"
  { echo "=== SIGNAL(run_with_err) ==="; echo "TIME: $(date -Is)"; echo "SIGNAL: $sig"; } >> "$RUN/last_trace.txt"
  echo "exit_code=$code" > "$ERRFILE"; mirror; print_paths; exit "$code"; }
trap 'on_sig SIGINT 130'  INT
trap 'on_sig SIGTERM 143' TERM

# 前置資訊
{ echo "[*] run_with_err start @ $TS"
  echo "[*] PWD=$(pwd)"
  echo "[*] CMD: $*"
  echo "[*] whoami=$(whoami)"
  echo "[*] df -h | head"; df -h | head -n 10 || true
  echo "[*] ulimit -a"; ulimit -a || true; } >> "$RUNLOG" 2>&1

# xtrace 輸出
exec 9>>"$XTRACE"
export BASH_XTRACEFD=9
export PS4='+ $(date "+%Y-%m-%dT%H:%M:%S%z") [${BASH_SOURCE##*/}:${LINENO}] '

# 用子殼層執行：就算內層炸也能拿到 rc
set +e
(
  set -Eeuo pipefail -o errtrace
  set -x
  if command -v stdbuf >/dev/null 2>&1; then stdbuf -oL -eL bash -lc "$*"
  else bash -lc "$*"; fi
) >>"$RUNLOG" 2>&1
ec=$?
set -e

# 鏡射 & 路徑
if [ $ec -ne 0 ]; then echo "exit_code=$ec" > "$ERRFILE"; else : > "$ERRFILE"; fi
mirror; print_paths

# 摘要
echo "[*] tail RUNLOG (last 60 lines)"; tail -n 60 "$RUNLOG" || true
echo "[*] tail XTRACE (last 40 lines)"; tail -n 40 "$XTRACE" || true
exit $ec

#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
CMD="${1:-start}"
TS="$(date +%Y%m%dT%H%M%S)"
RUN_DIR="reports_auto/api/${TS}"
LOG="$RUN_DIR/run.log"; ERR="$RUN_DIR/api.err"; PY_LAST="$RUN_DIR/py_last_trace.txt"; PIDF="$RUN_DIR/api.pid"
mkdir -p "$RUN_DIR" reports_auto/status reports_auto/.quarantine
source scripts/error_beacon.lib.sh 2>/dev/null || true
print_paths(){ echo "[PATHS]"; for k in RUN_DIR LOG ERR PY_LAST; do eval v=\$$k; printf "  %-6s= %s\n" "$k" "$(cd "$(dirname "$v")" && pwd)/$(basename "$v")"; done; }
on_err(){ c=${1:-$?}; { echo "=== BASH_TRAP ==="; echo "TIME: $(date -Is)"; echo "LAST:${BASH_COMMAND:-<none>}"; echo "CODE:$c"; } >>"$RUN_DIR/last_trace.txt"; echo "exit_code=$c" > "$ERR"; beacon_record_error "$RUN_DIR" "$ERR" "$PY_LAST"; print_paths; echo "[FATAL] api failed (code=$c)"; exit "$c"; }
on_exit(){ ln -sfn "$RUN_DIR" reports_auto/LATEST || true; beacon_record_run "$RUN_DIR"; print_paths; echo "[*] REPORT DIR ready"; command -v explorer.exe >/dev/null 2>&1 && explorer.exe "$(wslpath -w "$(cd "$RUN_DIR" && pwd)")" >/dev/null 2>&1 || true; }
trap 'on_err $?' ERR; trap on_exit EXIT

case "$CMD" in
  start)
    { exec > >(tee -a "$LOG") 2>&1; } || { exec >>"$LOG" 2>&1; }
    # 環境與 venv
    [ -f scripts/env.default ] && set -a && . scripts/env.default && set +a
    : "${SMA_DRY_RUN:=1}"; : "${PORT:=8000}"
    if command -v guard::venv_on >/dev/null 2>&1; then guard::venv_on || true; elif [ -f ".venv/bin/activate" ]; then . .venv/bin/activate; fi
    export PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 PYTHONPATH="src:vendor:${PYTHONPATH:-}" SMA_RUN_DIR="$RUN_DIR"
    echo "[*] DRY_RUN=$SMA_DRY_RUN  PORT=$PORT"
    # 起服（背景）
    nohup python -u scripts/http_api_min.py > "$LOG" 2>&1 &
    echo $! > "$PIDF"
    sleep 0.8
    echo "[*] PID=$(cat "$PIDF")"
    # 煙霧測試（不會中斷；結果落地 smoke.json）
    curl -sS -X POST "http://127.0.0.1:${PORT}/classify" -H "Content-Type: application/json" -d '{"texts":["您好我想詢問報價與交期","發票抬頭變更"],"route":"rule"}' > "$RUN_DIR/smoke.json" || true
    ;;
  stop)
    # 找最近一次 api.pid
    PIDFILE="$(ls -1dt reports_auto/api/2*/api.pid 2>/dev/null | head -n1 || true)"
    if [ -n "${PIDFILE:-}" ] && [ -f "$PIDFILE" ]; then
      PID="$(cat "$PIDFILE" || true)"; [ -n "${PID:-}" ] && kill "$PID" 2>/dev/null || true
      echo "[*] stopped PID=${PID:-NA} ($PIDFILE)"
    else
      echo "[WARN] no running pid file"; fi
    ;;
  status)
    ss -ltn 2>/dev/null | grep -E "LISTEN|:${PORT:-8000}\b" || true
    ;;
  *)
    echo "usage: $0 {start|stop|status}"; exit 2;;
esac

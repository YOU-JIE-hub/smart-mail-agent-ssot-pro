#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"; mkdir -p "$ERR_DIR"
set -a; [ -f scripts/env.default ] && . scripts/env.default || true; set +a
export SMA_ERR_DIR="$ERR_DIR"
PORT="${PORT:-8000}"
RUN_DIR="$ROOT/reports_auto/api/$(date +%Y%m%dT%H%M%S)"; mkdir -p "$RUN_DIR"
PIDFILE="$RUN_DIR/api.pid"; OUTLOG="$RUN_DIR/api.out"; ERRLOG="$RUN_DIR/api.err"

pick_server_py() {
  [ -f tools/api_server.py ] && { echo tools/api_server.py; return; }
  local c; c="$(ls -1 src/**/api_server.py 2>/dev/null | head -n1 || true)"
  [ -n "$c" ] && echo "$c" || echo ""
}

case "${1:-start}" in
  start)
    # 若已在跑，略過
    if [ -f "$PIDFILE" ] && ps -p "$(cat "$PIDFILE" 2>/dev/null)" >/dev/null 2>&1; then
      echo "[WARN] API already running pid=$(cat "$PIDFILE")"; exit 0; fi
    SFILE="$(pick_server_py)"
    if [ -z "$SFILE" ]; then echo "[FATAL] api_server.py not found" | tee -a "$ERR_DIR/api.err"; exit 86; fi
    # 先殺掉可能殘留的 8000/8088
    fuser -k -n tcp 8000 2>/dev/null || true
    fuser -k -n tcp 8088 2>/dev/null || true
    # 背景啟動（強制 uvicorn 優先）→ 寫 pidfile
    ( nohup "$SHELL" -lc "exec python -u vendor/sma_tools/force_uvicorn_runner.py '$SFILE'" >\"$OUTLOG\" 2>\"$ERRLOG\" & echo \$! >\"$PIDFILE\" ) </dev/null >/dev/null 2>&1
    # 等待就緒（最多 10s），先等 $PORT，再等 8088（回退）
    ok=""
    for i in $(seq 1 50); do ss -ltn 2>/dev/null | grep -q \":${PORT}\\b\" && { ok="$PORT"; break; }; sleep 0.2; done
    if [ -z "$ok" ]; then
      for i in $(seq 1 50); do ss -ltn 2>/dev/null | grep -q \":8088\\b\" && { ok="8088"; break; }; sleep 0.2; done
    fi
    if [ -n "$ok" ]; then
      echo "[API] http://127.0.0.1:${ok}"
      echo "$ok" > "$RUN_DIR/actual_port"
      exit 0
    else
      echo "[FATAL] API not listening on $PORT nor 8088" | tee -a "$ERR_DIR/api.err"; exit 87
    fi
    ;;
  stop)
    if [ -f "$PIDFILE" ]; then kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE"; fi
    fuser -k -n tcp "$PORT" 2>/dev/null || true
    fuser -k -n tcp 8088 2>/dev/null || true
    echo "[*] api_down done"
    ;;
  status)
    ss -ltn 2>/dev/null | grep -E "LISTEN|:${PORT}\b|:8088\b" || true
    ;;
  *)
    echo "usage: $0 {start|stop|status}"; exit 2;;
esac

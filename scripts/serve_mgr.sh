#!/usr/bin/env bash
set -Eeuo pipefail
cmd="${1:-}"; LOG_DIR="reports_auto/serve"; mkdir -p "$LOG_DIR"
PORT="${PORT:-8000}"; HOST="${HOST:-0.0.0.0}"; APP="${APP:-service.app:app}"
PID_FILE="$LOG_DIR/uvicorn.pid"
log(){ printf "[%s] %s\n" "$(date -u +%FT%TZ)" "$*"; }
py_port_check(){ python - "$PORT" <<PY 2>/dev/null || exit 1
import socket,sys; p=int(sys.argv[1]); s=socket.socket();
try: s.bind(("127.0.0.1",p));
except OSError: sys.exit(1)
finally: s.close()
PY
}
is_running(){ [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; }
start(){
  ts="$(date -u +%Y%m%dT%H%M%S)"; LOG_FILE="$LOG_DIR/uvicorn_${ts}.log"; ln -sfn "$LOG_FILE" "$LOG_DIR/current.log"
  # 將之後所有輸出導到 log（包含早期錯誤）
  exec >>"$LOG_FILE" 2>&1
  echo "timestamp: $(date -u +%F\ %T)Z"; uname -a || true; python -V || true
  trap 'code=$?; echo "[FATAL] trapped exit $code"; ' EXIT
  if is_running; then log "already running pid=$(cat "$PID_FILE")"; exit 0; fi
  if ! py_port_check; then log "PORT $PORT already in use"; exit 2; fi
  [[ -n "${INTENT_PKL:-}" && ! -f "$INTENT_PKL" ]] && log "WARN INTENT_PKL=$INTENT_PKL not found" || true
  [[ -n "${SPAM_PKL:-}"   && ! -f "$SPAM_PKL"   ]] && log "WARN SPAM_PKL=$SPAM_PKL not found"   || true
  log "starting: uvicorn $APP on $HOST:$PORT"
  if command -v setsid >/dev/null 2>&1; then RUNNER=(setsid); else RUNNER=(nohup); fi
  "${RUNNER[@]}" uvicorn "$APP" --host "$HOST" --port "$PORT" --access-log &
  echo $! >"$PID_FILE"
  sleep 1
  if ! is_running; then log "uvicorn died immediately"; exit 1; fi
  # 健康檢查
  if command -v curl >/dev/null 2>&1; then curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null || true
  else python - "$PORT" <<PY >/dev/null 2>&1 || true
import os,sys,urllib.request; p=sys.argv[1];
sys.exit(0 if urllib.request.urlopen(f"http://127.0.0.1:{p}/health", timeout=2).read() else 1)
PY
  fi
  log "started OK pid=$(cat "$PID_FILE"); log=$LOG_FILE"
}
stop(){
  if is_running; then pid="$(cat "$PID_FILE")"; log "stopping $pid"; kill "$pid" 2>/dev/null || true; sleep 1; kill -9 "$pid" 2>/dev/null || true; rm -f "$PID_FILE"; log "stopped";
  else log "no running pid; try freeing port if occupied"
       python - "$PORT" <<PY >/dev/null 2>&1 || true
import psutil,sys
p=int(sys.argv[1])
for proc in psutil.process_iter(attrs=["pid","name","connections"]):
  try:
    for c in proc.connections(kind="inet"):
      if c.laddr and c.laddr.port==p and c.status=="LISTEN": proc.kill()
  except Exception: pass
PY
       sleep 1; log "done";
  fi
}
status(){ if is_running; then log "RUNNING pid=$(cat "$PID_FILE") port=$PORT"; else log "STOPPED"; fi; [[ -f "$LOG_DIR/current.log" ]] && log "LOG: $LOG_DIR/current.log" || true; }
tail(){ [[ -f "$LOG_DIR/current.log" ]] || { echo "no current.log yet" >&2; exit 1; }; tail -n +1 -F "$LOG_DIR/current.log"; }
case "$cmd" in start) start ;; stop) stop ;; restart) stop; start ;; status) status ;; tail) tail ;; *) echo "Usage: $0 {start|stop|restart|status|tail}" >&2; exit 2 ;; esac

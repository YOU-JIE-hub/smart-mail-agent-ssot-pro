#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

# venv (if exists)
[[ -f .venv/bin/activate ]] && . .venv/bin/activate || true

ACTION="${1:-start}"
PORT="${PORT:-8000}"
LOG="/tmp/sma_uv_${PORT}.log"
PIDF="/tmp/sma_uv_${PORT}.pid"

port_pid() {
  # lsof first
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1 && return 0 || true
  fi
  # ss fallback
  if command -v ss >/dev/null 2>&1; then
    ss -lntp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print $NF}' | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -1 && return 0 || true
  fi
  return 1
}

is_alive() {
  local pid="$1"
  [[ -n "$pid" ]] && ps -p "$pid" >/dev/null 2>&1
}

start() {
  # already running?
  if [[ -f "$PIDF" ]]; then
    local pid; pid="$(cat "$PIDF" || true)"
    if is_alive "$pid"; then
      echo "[OK] uvicorn already running on :$PORT (pid=$pid). LOG=$LOG"
      exit 0
    fi
  fi
  # port in use by someone else?
  local ppid; ppid="$(port_pid || true)"
  if [[ -n "$ppid" ]]; then
    echo "[WARN] port :$PORT in use by pid=$ppid. Use '$0 stop' or set another PORT."
    exit 1
  fi
  echo "[INFO] starting uvicorn on :$PORT ..."
  nohup env PORT="$PORT" uvicorn service.app:app --host 0.0.0.0 --port "$PORT" --access-log >"$LOG" 2>&1 &
  echo $! > "$PIDF"

  # wait for health
  for i in $(seq 1 40); do
    if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; then
      echo "[OK] started. PID=$(cat "$PIDF"), LOG=$LOG"
      exit 0
    fi
    sleep 0.25
  done
  echo "[ERR] server failed to become healthy on :$PORT"
  tail -n 120 "$LOG" || true
  exit 1
}

stop() {
  local pid=""
  [[ -f "$PIDF" ]] && pid="$(cat "$PIDF" || true)"
  if is_alive "$pid"; then
    echo "[INFO] stopping pid=$pid ..."
    kill "$pid" || true
    sleep 0.5
    is_alive "$pid" && kill -9 "$pid" || true
  else
    # try by port
    local ppid; ppid="$(port_pid || true)"
    if [[ -n "$ppid" ]]; then
      echo "[INFO] stopping port:$PORT pid=$ppid ..."
      kill "$ppid" || true
      sleep 0.5
      is_alive "$ppid" && kill -9 "$ppid" || true
    else
      echo "[OK] nothing to stop on :$PORT"
    fi
  fi
  rm -f "$PIDF"
  echo "[OK] stopped :$PORT"
}

status() {
  local pid=""
  [[ -f "$PIDF" ]] && pid="$(cat "$PIDF" || true)"
  if is_alive "$pid"; then
    echo "[OK] running pid=$pid on :$PORT (PIDF=$PIDF, LOG=$LOG)"
    exit 0
  fi
  local ppid; ppid="$(port_pid || true)"
  if [[ -n "$ppid" ]]; then
    echo "[WARN] port :$PORT busy by pid=$ppid (not our PIDF)."
    exit 1
  fi
  echo "[OK] not running on :$PORT"
}

tail_log() {
  [[ -f "$LOG" ]] || { echo "[INFO] no log yet: $LOG"; exit 0; }
  tail -f "$LOG"
}

case "$ACTION" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  tail) tail_log ;;
  *) echo "Usage: $0 {start|stop|restart|status|tail}"; exit 2 ;;
esac

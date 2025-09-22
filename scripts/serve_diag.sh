#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"
[[ -f .venv/bin/activate ]] && . .venv/bin/activate || true
ACTION="${1:-diag}"
PORT="${PORT:-8000}"
TS="$(date -u +%Y%m%dT%H%M%S)"
PDIR="reports_auto/panic_${TS}_serve"
mkdir -p "$PDIR"
UVLOG="$PDIR/uvicorn.log"
RUNLOG="$PDIR/run.log"
RUNERR="$PDIR/run.err"
PIDF="$PDIR/pid"
echo "[PANIC] DIR: $PDIR" | tee -a "$RUNLOG"

port_pid() {
  if command -v lsof >/dev/null 2>&1; then lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1; return 0; fi
  if command -v ss   >/dev/null 2>&1; then ss -lntp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print $NF}' | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -1; return 0; fi
  return 1
}
is_alive(){ [[ -n "${1:-}" ]] && ps -p "$1" >/dev/null 2>&1; }

diag_env(){
  { echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"; uname -a;
    echo "--- python"; python -V 2>&1;
    echo "--- pip list (top 40)"; python -m pip list --format=columns 2>/dev/null | head -40;
    echo "--- env whitelist"; env | egrep -i "^(PORT|INTENT_PKL|SPAM_PKL|PYTHONPATH|PYTHONNOUSERSITE|VIRTUAL_ENV)=" || true;
    echo "--- which uvicorn"; command -v uvicorn || true;
  } >"$PDIR/env.txt" 2>&1
  { echo "--- ps aux (uvicorn)"; ps aux | egrep -i "uvicorn|python" | egrep -v "egrep" || true;
    echo; echo "--- listeners on :$PORT"; (command -v lsof >/dev/null && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN || true);
    (command -v ss >/dev/null && echo && ss -lntp || true);
  } >"$PDIR/ps.txt" 2>&1
  : >"$PDIR/net.txt"
}

start_server(){
  local holder; holder="$(port_pid || true)"
  if [[ -n "$holder" ]]; then
    echo "[WARN] port :$PORT already in use by pid=$holder" | tee -a "$RUNERR"
    return 1
  fi
  echo "[INFO] starting uvicorn :$PORT" | tee -a "$RUNLOG"
  nohup env PORT="$PORT" uvicorn service.app:app --host 0.0.0.0 --port "$PORT" --access-log >"$UVLOG" 2>&1 &
  echo $! > "$PIDF"
  for i in $(seq 1 40); do
    if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
      echo "[OK] healthy on :$PORT (pid=$(cat "$PIDF"))" | tee -a "$RUNLOG"
      return 0
    fi
    sleep 0.25
  done
  echo "[ERR] health check failed on :$PORT" | tee -a "$RUNERR"
  return 2
}

stop_server(){
  local pid=""; [[ -f "$PIDF" ]] && pid="$(cat "$PIDF" || true)"
  if is_alive "$pid"; then kill "$pid" || true; sleep 0.5; is_alive "$pid" && kill -9 "$pid" || true; fi
  local holder; holder="$(port_pid || true)";
  if [[ -n "$holder" ]]; then kill "$holder" || true; sleep 0.5; is_alive "$holder" && kill -9 "$holder" || true; fi
  echo "[OK] stopped :$PORT" | tee -a "$RUNLOG"
}

case "$ACTION" in
  start)
    diag_env; start_server || true; echo "$PDIR" ;;
  stop)
    stop_server; echo "$PDIR" ;;
  status)
    diag_env; holder="$(port_pid || true)"; if [[ -n "$holder" ]]; then echo "[OK] port:$PORT pid=$holder"; else echo "[OK] idle"; fi; echo "$PDIR" ;;
  tail)
    [[ -f "$UVLOG" ]] || { echo "[INFO] no log yet: $UVLOG"; exit 0; }; tail -f "$UVLOG" ;;
  diag|*)
    diag_env;
    if start_server; then
      echo "[DIAG] server up. copying logs snapshot..." | tee -a "$RUNLOG"
      sed -n "1,200p" "$UVLOG" > "$PDIR/uvicorn.head.txt" 2>/dev/null || true
      echo "$PDIR"
      exit 0
    else
      echo "[DIAG] start failed, snapshot below" | tee -a "$RUNERR"
      { echo "--- uvicorn.log (tail)"; tail -n 200 "$UVLOG" 2>/dev/null || true; } >> "$RUNERR"
      echo "$PDIR"
      exit 1
    fi ;;
esac

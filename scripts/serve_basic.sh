#!/usr/bin/env bash
# 常駐啟停；不做健康檢查；絕不自殺
set -Eeuo pipefail
SELF="${BASH_SOURCE[0]-$0}"
ROOT="$(cd "$(dirname "$SELF")/.." && pwd 2>/dev/null || pwd)"
cd "$ROOT" || { echo "[FATAL] cannot cd $ROOT"; exit 2; }

ENV_FILE="${ENV_FILE:-.env}"
PORT="${PORT:-8000}"
PIDF="reports_auto/serve/uvicorn.pid"
LOGD="reports_auto/serve"
mkdir -p "$LOGD" || true

ensure_env() {
  [[ -f "$ENV_FILE" ]] && return 0
  cat >"$ENV_FILE" <<EOF
INTENT_PKL=/home/youjie/projects/smart-mail-agent-ssot-pro/models/spam/artifacts/model_pipeline.pkl
SPAM_PKL=/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl
PORT=$PORT
PYTHONUNBUFFERED=1
EOF
  echo "[HINT] wrote default $ENV_FILE"
}

start() {
  if ss -lptn "sport = :$PORT" >/dev/null 2>&1; then echo "[OK] already listening on :$PORT"; exit 0; fi
  ensure_env
  LOG="$LOGD/uvicorn.$(date -u +%Y%m%dT%H%M%S).log"
  echo "[RUN] uvicorn :$PORT (log: $LOG)"
  nohup ./.venv/bin/python -m uvicorn service.app:app \
    --env-file "$ENV_FILE" --host 127.0.0.1 --port "$PORT" \
    --log-level info --access-log >>"$LOG" 2>&1 &
  echo $! > "$PIDF"
  disown || true
  echo "[OK] pid $(cat "$PIDF")"
}

stop() {
  if [[ -s "$PIDF" ]]; then pid="$(cat "$PIDF")"; kill "$pid" 2>/dev/null || true; sleep 1; kill -9 "$pid" 2>/dev/null || true; rm -f "$PIDF"; echo "[OK] stopped (pid $pid)";
  else pids="$(lsof -tiTCP:$PORT -sTCP:LISTEN 2>/dev/null || true)"; [[ -n "$pids" ]] && kill $pids 2>/dev/null || true; [[ -n "$pids" ]] && kill -9 $pids 2>/dev/null || true; echo "[OK] stopped (no pidfile)"; fi
}

status() { ss -lptn "sport = :$PORT" || echo "[NG] not listening"; }
tailf()  { tail -n 100 -F "$LOGD"/uvicorn.*.log; }

case "${1:-}" in
  start) start ;; stop) stop ;; restart) stop; start ;;
  status) status ;; tail) tailf ;;
  *) echo "Usage: $0 {start|stop|restart|status|tail}"; exit 2 ;;
esac

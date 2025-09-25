#!/usr/bin/env bash
set -Eeuo pipefail
SELF="${BASH_SOURCE[0]-$0}"
ROOT="$(cd "$(dirname "$SELF")/.." && pwd 2>/dev/null || pwd)"
cd "$ROOT" || { echo "[FATAL] cannot cd $ROOT"; exit 2; }

SESSION="${SESSION:-sma}"
ENV_FILE="${ENV_FILE:-.env}"
PORT="${PORT:-8000}"
LOGD="reports_auto/serve"
mkdir -p "$LOGD"

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
  ensure_env
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[OK] tmux session '$SESSION' already running"; exit 0
  fi
  local LOG="$LOGD/tmux.$(date -u +%Y%m%dT%H%M%S).log"
  tmux new -d -s "$SESSION"
  tmux send-keys -t "$SESSION" "
cd '$ROOT';
ENV_FILE='$ENV_FILE' PORT='$PORT' ./.venv/bin/python -X faulthandler -m uvicorn service.app:app \
  --env-file \"\$ENV_FILE\" --host 127.0.0.1 --port \"\$PORT\" \
  --log-level info --access-log 2>&1 | tee -a '$LOG'
" C-m
  sleep 1
  echo "[OK] started tmux:$SESSION (log -> $LOG)"
}

stop() {
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  echo "[OK] stopped tmux:$SESSION"
}

status() {
  ss -lptn "sport = :$PORT" || echo "[NG] not listening on :$PORT"
  tmux has-session -t "$SESSION" 2>/dev/null && echo "[OK] tmux:$SESSION running" || echo "[NG] no tmux session"
}

tail() {
  tmux capture-pane -pt "$SESSION" | tail -n 80
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  tail) tail ;;
  *) echo "Usage: $0 {start|stop|restart|status|tail}"; exit 2 ;;
esac

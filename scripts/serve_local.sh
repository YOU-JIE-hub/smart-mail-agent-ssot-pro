#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
[ -f .env ] && set -a && . .env && set +a
export PORT="${PORT:-8000}"
echo "[ENV] INTENT_PKL=${INTENT_PKL:-<none>}  SPAM_PKL=${SPAM_PKL:-<none>}"
log="reports_auto/serve/uvicorn.$(date -u +%Y%m%dT%H%M%S).log"
echo "[RUN] uvicorn :$PORT  (log -> $log)"
python -m uvicorn service.app:app --host 127.0.0.1 --port "$PORT" --log-level info \
  2>&1 | tee "$log"

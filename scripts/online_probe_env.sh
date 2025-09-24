#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

set -a; . ./.env 2>/dev/null || true; set +a
HOST="${HOST:-127.0.0.1}"; PORT="${PORT:-18080}"; APP="${APP:-sma.api.service_compat:app}"

TS="$(date +%Y%m%dT%H%M%S)"; OUT="reports_auto/online/$TS"; mkdir -p "$OUT"; ln -sfn "$OUT" reports_auto/online/latest
log(){ echo "[$(date -Iseconds)] $*" | tee -a "$OUT/run.log"; }
dump(){ n="$1"; shift; set +e; code="$(curl -sS -D "$OUT/${n}.hdr" -o "$OUT/${n}.body" -w '%{http_code}' "$@")"; rc=$?; set -e; echo -n "${code:-NA}" > "$OUT/${n}.code"; printf "%-14s %s\n" "$n" "$(cat "$OUT/${n}.code")" | tee -a "$OUT/run.log"; return $rc; }

# 關舊服務
pkill -f "uvicorn .*:${PORT}" 2>/dev/null || true; ( command -v fuser >/dev/null && fuser -k "${PORT}/tcp" ) || true; sleep 0.3

# 啟動
log "[RUN] uvicorn ${APP} --host ${HOST} --port ${PORT}"
uvicorn "${APP}" --host "${HOST}" --port "${PORT}" --log-level warning >"$OUT/uvicorn.out" 2>"$OUT/uvicorn.err" & echo -n $! > "$OUT/uvicorn.pid"

# 等 ready
for i in $(seq 1 50); do code="$(curl -s -o /dev/null -w '%{http_code}' "http://${HOST}:${PORT}/readyz" || true)"; [ "$code" = "200" ] && break; sleep 0.2; done
dump readyz        "http://${HOST}:${PORT}/readyz"
dump debug_models  "http://${HOST}:${PORT}/debug/models"
dump intent        -H 'Content-Type: application/json' -d '{"text":"請問退款流程？"}' "http://${HOST}:${PORT}/v1/predict/intent"
dump spam          -H 'Content-Type: application/json' -d '{"text":"Win a FREE PRIZE!!!"}' "http://${HOST}:${PORT}/v1/predict/spam"
dump kie           "http://${HOST}:${PORT}/v1/kie/health" || true

# 校驗 intent_path 與 .env 對齊
ENV_INTENT="$(printf "%s" "${INTENT_PKL:-}")"
if command -v jq >/dev/null 2>&1; then
  SRV_INTENT="$(jq -r '.intent_pkl // .intent_path // .intent_meta.path // empty' "$OUT/debug_models.body" 2>/dev/null || true)"
else
  SRV_INTENT="$(sed -n '1,200p' "$OUT/debug_models.body" | sed -n 's/.*"intent_\(pkl\|path\)":"\([^"]*\)".*/\2/p' | head -n1)"
fi

if [ -n "$ENV_INTENT" ] && [ -n "$SRV_INTENT" ] && [ "$ENV_INTENT" != "$SRV_INTENT" ]; then
  echo "[FAIL] intent_path mismatch" | tee -a "$OUT/run.log"
  echo "  .env INTENT_PKL = $ENV_INTENT" | tee -a "$OUT/run.log"
  echo "  srv intent_path = $SRV_INTENT" | tee -a "$OUT/run.log"
  exit 32
fi

log "OK: intent_path aligned: ${SRV_INTENT:-<unknown>}"
echo "$OUT"

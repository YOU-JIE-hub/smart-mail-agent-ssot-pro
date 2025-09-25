#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
cd "$(dirname "$0")/.." || exit 2
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

TS="$(date +%Y%m%dT%H%M%S)"; OUT="reports_auto/online/${TS}"; mkdir -p "$OUT"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"

python - <<'PY' || python -m pip install -q "uvicorn[standard]" fastapi
import importlib; importlib.import_module("fastapi"); importlib.import_module("uvicorn"); print("OK")
PY

uvicorn sma.api.shim_app:app --host 127.0.0.1 --port 8000 --log-level warning >"$OUT/uvicorn.out" 2>"$OUT/uvicorn.err" &
API_PID=$!

for i in $(seq 1 25); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$API_BASE/readyz" || true)"
  [ "$code" = "200" ] && break
  sleep 1
done

{
  echo "# Online Smoke"
  for ep in health healthz ready readyz; do
    code="$(curl -s -o /dev/null -w '%{http_code}' "$API_BASE/$ep" || true)"
    echo "- /$ep：$([ "$code" = "200" ] && echo "**OK**" || echo "**FAIL($code)**")"
  done
  code="$(curl -s -o "$OUT/spam.json"   -w '%{http_code}' -H 'Content-Type: application/json' -d '{"text":"Win a FREE prize!!!"}' "$API_BASE/v1/predict/spam"   || true)"
  echo "- /v1/predict/spam：$([ "$code" = "200" ] && echo "**OK**" || echo "**FAIL($code)**")"
  code="$(curl -s -o "$OUT/intent.json" -w '%{http_code}' -H 'Content-Type: application/json' -d '{"text":"請問退款流程？"}'      "$API_BASE/v1/predict/intent" || true)"
  echo "- /v1/predict/intent：$([ "$code" = "200" ] && echo "**OK**" || echo "**FAIL($code)**")"
  code="$(curl -s -o "$OUT/kie.json"    -w '%{http_code}' -H 'Content-Type: application/json' -d '{"text":"金額 12,500；聯絡 0912-345-678；mail a@b.com"}' "$API_BASE/v1/predict/kie" || true)"
  echo "- /v1/predict/kie：$([ "$code" = "200" ] && echo "**OK**" || echo "**FAIL($code)**")"
} > "$OUT/online_smoke.md"

kill "$API_PID" 2>/dev/null || true
echo "[OK] Online Smoke -> $OUT/online_smoke.md"

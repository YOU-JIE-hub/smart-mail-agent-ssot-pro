#!/usr/bin/env bash
set -Eeuo pipefail
PORT="${PORT:-8000}"

echo "[CHK] /ready"
curl -sS "http://127.0.0.1:$PORT/ready"  | python -m json.tool
echo "[CHK] /health"
curl -sS "http://127.0.0.1:$PORT/health" | python -m json.tool

echo "[SMOKE] spam"
curl -sS "http://127.0.0.1:$PORT/v1/predict" \
  -H 'content-type: application/json' \
  -d '{"task":"spam","text":"FREE $$$ CLICK http://spam","top_k":2}' | python -m json.tool

echo "[SMOKE] intent"
curl -sS "http://127.0.0.1:$PORT/v1/predict" \
  -H 'content-type: application/json' \
  -d '{"task":"intent","text":"我要查詢訂單出貨進度","top_k":3}' | python -m json.tool

echo "[LOAD] 併發 80 * 16"
ok=0; total=80
seq "$total" | xargs -I{} -P 16 sh -c '
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:'"$PORT"'/v1/predict" \
    -H "content-type: application/json" \
    -d "{\"task\":\"spam\",\"text\":\"FREE $$$ CLICK http://spam\",\"top_k\":2}")
  echo $code
' | awk '{ if ($1=="200") ok++ } END { printf("[LOAD] 200 count: %d/%d\n", ok, '"$total"'); }'

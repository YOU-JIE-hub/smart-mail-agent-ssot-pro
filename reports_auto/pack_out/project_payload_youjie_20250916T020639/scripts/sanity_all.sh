#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
PORT="${PORT:-$(grep -E '^PORT=' scripts/env.default 2>/dev/null | tail -n1 | cut -d= -f2 || echo 8000)}"
API_DIR="$(ls -1dt reports_auto/api/2* 2>/dev/null | head -n1 || true)"
[ -n "$API_DIR" ] || API_DIR="reports_auto/api/$(date +%Y%m%dT%H%M%S)"; mkdir -p "$API_DIR"
jqok(){ command -v jq >/dev/null 2>&1; }
echo "[*] Using API_DIR: $(cd "$API_DIR" && pwd)"; echo "[*] PORT=$PORT"
for route in rule ml; do
  out="$API_DIR/sanity_smoke_${route}.json"; echo "[*] smoke $route -> $out"
  curl -sS -X POST "http://127.0.0.1:${PORT}/classify" -H 'Content-Type: application/json' \
    -d '{"texts":["想詢問報價與交期","需要技術支援"],"route":"'"$route"'"}' > "$out" || true
  if jqok; then jq . "$out" || true; else cat "$out" || true; fi
done
TRI="$API_DIR/sanity_tri_eval.json"; echo "[*] /tri-eval -> $TRI"
curl -sS -X POST "http://127.0.0.1:${PORT}/tri-eval" -H 'Content-Type: application/json' \
  -d '{"texts":["想詢問報價與交期","需要技術支援","發票抬頭更新"],"labels":["biz_quote","tech_support","profile_update"]}' > "$TRI" || true
if jqok; then jq . "$TRI" || true; else cat "$TRI" || true; fi
echo "[PATHS]"
echo "  RUN_DIR = $(cd "$API_DIR"&&pwd)"
echo "  LOG     = $(cd "$API_DIR"&&pwd)/run.log"
echo "  ERR     = $(cd "$API_DIR"&&pwd)/api.err"
echo "  PY_LAST = $(cd "$API_DIR"&&pwd)/py_last_trace.txt"
echo "  SERVER  = $(cd "$API_DIR"&&pwd)/server.log"
echo "  SMOKE_R = $(cd "$API_DIR"&&pwd)/sanity_smoke_rule.json"
echo "  SMOKE_M = $(cd "$API_DIR"&&pwd)/sanity_smoke_ml.json"
echo "  TRI_OUT = $(cd "$API_DIR"&&pwd)/sanity_tri_eval.json"

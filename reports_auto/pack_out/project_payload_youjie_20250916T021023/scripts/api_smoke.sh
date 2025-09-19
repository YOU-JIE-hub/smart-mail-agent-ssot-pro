#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="${ROOT:-/home/youjie/projects/smart-mail-agent-ssot-pro}"; cd "$ROOT"; PORT="${PORT:-8000}"
echo "[*] smoke @ :$PORT"
curl -sS -X POST "http://localhost:${PORT}/classify" -H 'Content-Type: application/json' -d '{"texts":["想詢問報價與交期","需要技術支援"],"route":"rule"}' | tee reports_auto/status/smoke_rule.json >/dev/null
curl -sS -X POST "http://localhost:${PORT}/classify" -H 'Content-Type: application/json' -d '{"texts":["想詢問報價與交期","需要技術支援"],"route":"ml"}'   | tee reports_auto/status/smoke_ml.json   >/dev/null

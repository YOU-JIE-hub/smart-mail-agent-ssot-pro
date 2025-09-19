#!/usr/bin/env bash
# - 產出：reports_auto/api_smoke/<TS>/{run.log,smoke.json,tri.json}，失敗寫 smoke.err
# - 規則：set -Eeuo pipefail、單一錯誤檔、時間戳目錄、結尾必印路徑、建立 LATEST
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/api_smoke/${TS}"
LOG="$OUT/run.log"; ERR="$OUT/smoke.err"
mkdir -p "$OUT" reports_auto/status reports_auto/.quarantine
exec > >(tee -a "$LOG") 2>&1

on_err(){ c=${1:-$?}; { echo "=== BASH_TRAP ==="; echo "TIME: $(date -Is)"; echo "LAST:${BASH_COMMAND:-<none>}"; echo "CODE:$c"; } >"$ERR" || true; exit "$c"; }
on_exit(){ ln -sfn "$OUT" reports_auto/LATEST || true; echo "[*] REPORT DIR: $(cd "$OUT" && pwd)"; if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$OUT")" >/dev/null 2>&1 || true; fi; }
trap 'on_err $?' ERR; trap on_exit EXIT

PORT="${PORT:-8000}"
echo "[*] Smoke against :${PORT}"

# A) 規則路由（一定要回 200）
curl -sS -X POST "http://127.0.0.1:${PORT}/classify" -H 'Content-Type: application/json' \
  -d '{"texts":["想詢問報價與交期","發票抬頭要更新"], "route":"rule"}' | tee "$OUT/smoke_rule.json" >/dev/null

# B) ML 路由（若模型或相依不齊會 5xx；trace 會在 PY_LAST）
curl -sS -X POST "http://127.0.0.1:${PORT}/classify" -H 'Content-Type: application/json' \
  -d '{"texts":["想詢問報價與交期","需要技術支援"], "route":"ml"}' | tee "$OUT/smoke_ml.json" >/dev/null || true

# C) 輕量 /tri-eval（附上標籤計 accuracy）
curl -sS -X POST "http://127.0.0.1:${PORT}/tri-eval" -H 'Content-Type: application/json' \
  -d '{"texts":["想詢問報價與交期","需要技術支援","發票抬頭更新"], "labels":["biz_quote","tech_support","profile_update"]}' \
  | tee "$OUT/tri.json" >/dev/null || true

# D) 摘要（寫入 reports_auto/status/INTENTS_API_<TS>.md）
MD="reports_auto/status/INTENTS_API_${TS}.md"
{
  echo "# INTENTS_API_${TS}"
  echo "- RULE_RESP: $(cd "$OUT" && pwd)/smoke_rule.json"
  echo "- ML_RESP  : $(cd "$OUT" && pwd)/smoke_ml.json"
  echo "- TRI_RESP : $(cd "$OUT" && pwd)/tri.json"
  LASTAPI="$(ls -1dt reports_auto/api/2* 2>/dev/null | head -n1 || true)"
  if [ -n "$LASTAPI" ]; then
    AP="$(cd "$LASTAPI" && pwd)"
    echo "- API_RUN  : $AP"
    echo "- API_LOG  : $AP/run.log"
    echo "- API_ERR  : $AP/api.err"
    echo "- API_PYLAST: $AP/py_last_trace.txt"
  fi
} > "$MD"

echo "[OK] smoke 完成"

#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-18080}"
APP="${APP:-sma.api.service_compat:app}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/online/$TS"; mkdir -p "$OUT"; ln -sfn "$OUT" reports_auto/online/latest

log(){ echo "[$(date -Iseconds)] $*" | tee -a "$OUT/run.log"; }
finish(){
  rc=$?; log "EXIT rc=$rc"
  echo "OUT: $OUT"
  for x in readyz debug_models intent spam kie; do
    printf "%-14s %s\n" "$x" "$(cat "$OUT/$x.code" 2>/dev/null || echo NA)"
  done
  echo "See: $OUT/{*.code,*.hdr,*.body,uvicorn.out,uvicorn.err,run.log,import_check.json,py_compile.json,intent_offline.json}"
}
trap finish EXIT

dump(){ # dump <name> <curl args...>
  local n="$1"; shift
  set +e
  local code; code="$(curl -sS -D "$OUT/${n}.hdr" -o "$OUT/${n}.body" -w "%{http_code}" "$@")"
  local rc=$?
  set -e
  echo -n "${code:-NA}" > "$OUT/${n}.code"
  printf "%-14s %s\n" "$n" "$(cat "$OUT/${n}.code")" | tee -a "$OUT/run.log"
  return $rc
}

# 0) 快照 + import/syntax 檢查（失敗也落檔）
python - <<PY >"$OUT/import_check.json" 2>&1 || true
import json,traceback,importlib
res={}
try:
  svc=importlib.import_module("sma.api.service_compat"); res["service_compat"]=getattr(svc,"__file__",None)
  ic=importlib.import_module("sma.common.intent_compat"); res["intent_compat"]=getattr(ic,"__file__",None)
  res["status"]="ok"
except Exception as e:
  res={"status":"error","type":type(e).__name__,"message":str(e),"tb":traceback.format_exc()}
print(json.dumps(res,ensure_ascii=False,indent=2))
PY
python -m py_compile $(git ls-files "*.py" 2>/dev/null || echo) >"$OUT/py_compile.json" 2>&1 || true

# 1) 如果 18080 沒有在聽，就嘗試起 uvicorn（失敗也記錄，不中止）
if ! curl -s -o /dev/null "http://$HOST:$PORT/readyz"; then
  log "[RUN] uvicorn $APP --host $HOST --port $PORT"
  ( uvicorn "$APP" --host "$HOST" --port "$PORT" --log-level warning >"$OUT/uvicorn.out" 2>"$OUT/uvicorn.err" & echo $! >"$OUT/uvicorn.pid" ) || true
  # 等最多 6 秒
  for i in 1 2 3 4 5 6; do
    sleep 1
    curl -s -o /dev/null "http://$HOST:$PORT/readyz" && break || true
  done
else
  log "[INFO] Detected server listening on :$PORT (skip launching)"
fi

# 2) HTTP 探測（每個都產生 *.code/*.hdr/*.body）
dump readyz        "http://$HOST:$PORT/readyz"
dump debug_models  "http://$HOST:$PORT/debug/models"
dump intent        -H "Content-Type: application/json" -d "{\"text\":\"請問退款流程？\"}" "http://$HOST:$PORT/v1/predict/intent"
dump spam          -H "Content-Type: application/json" -d "{\"text\":\"Win a FREE PRIZE!!!\"}" "http://$HOST:$PORT/v1/predict/spam"
# KIE 健檢：先問 /v1/kie/health，若 404 再 hit /v1/predict/kie（都落檔）
code="$(curl -s -o /dev/null -w "%{http_code}" "http://$HOST:$PORT/v1/kie/health" || echo NA)"
if [ "$code" = "200" ]; then
  dump kie        "http://$HOST:$PORT/v1/kie/health"
else
  dump kie        -H "Content-Type: application/json" -d "{\"text\":\"發票 AA123456 日期 2024/11/02 金額 NT$12,500\"}" "http://$HOST:$PORT/v1/predict/kie"
fi

# 3) 離線意圖檢查（成功與否都寫）
python - <<PY >"$OUT/intent_offline.json" 2>&1 || true
import os,json,traceback
try:
  from sma.common.intent_compat import load_pipeline,predict_proba_batch,meta
  p=os.getenv("INTENT_PKL") or ""
  if not p: raise RuntimeError("INTENT_PKL empty")
  load_pipeline(p)
  proba,classes=predict_proba_batch(["請問退款流程？","我要申訴","請報價"])
  print(json.dumps({"path":p,"classes":classes,"shape":getattr(proba,"shape",None),"row0_max":float(getattr(proba,"max")() if hasattr(proba,"max") else 0)},ensure_ascii=False,indent=2))
except Exception as e:
  print(json.dumps({"offline_error":{"type":type(e).__name__,"message":str(e)}},ensure_ascii=False,indent=2))
PY

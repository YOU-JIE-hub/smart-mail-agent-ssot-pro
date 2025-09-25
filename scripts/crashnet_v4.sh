#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

HOST="${HOST:-127.0.0.1}"; PORT="${PORT:-18080}"
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
  echo "See: $OUT/{*.code,*.hdr,*.body,uvicorn.out,uvicorn.err,import_check.json,py_compile.json,intent_offline.json}"
}
trap finish EXIT

dump(){ # dump <name> <curl args...>
  local n="$1"; shift
  set +e
  local code; code="$(curl -sS -D "$OUT/${n}.hdr" -o "$OUT/${n}.body" -w '%{http_code}' "$@")"
  set -e
  echo -n "${code:-NA}" > "$OUT/${n}.code"
}

# env snapshot
python - <<'PY' >"$OUT/env.json"
import os, sys, json, platform
print(json.dumps({
  "cwd": os.getcwd(),
  "python": sys.version,
  "platform": platform.platform(),
  "env": {k: os.getenv(k) for k in ("INTENT_PKL","SPAM_PKL","KIE_DIR","PYTHONPATH")},
  "sys_path_head": sys.path[:6],
}, ensure_ascii=False, indent=2))
PY

# compile & imports
python - <<'PY' >"$OUT/py_compile.json" || true
import json, py_compile, traceback
files=["src/sma/api/service_compat.py","src/sma/common/intent_compat.py","src/sma/common/rules_features.py"]
res={}
for f in files:
  try: py_compile.compile(f, doraise=True); res[f]="ok"
  except Exception as e: res[f]={"error":type(e).__name__,"msg":str(e)}
print(json.dumps(res, ensure_ascii=False, indent=2))
PY

python - <<'PY' >"$OUT/import_check.json" || true
import json, importlib, traceback
out={}
for m in ("sma.api.service_compat","sma.common.intent_compat"):
  try:
    mod=importlib.import_module(m); out[m]={"status":"ok","file":getattr(mod,"__file__",None)}
  except Exception as e:
    out[m]={"status":"error","type":type(e).__name__,"msg":str(e)}
print(json.dumps(out, ensure_ascii=False, indent=2))
PY

# offline sanity (不依賴服務)
python - <<'PY' >"$OUT/intent_offline.json" || true
import os, json, traceback
out={"env_INTENT_PKL": os.getenv("INTENT_PKL")}
try:
  from sma.common.intent_compat import load_pipeline, predict_proba_batch, meta
  p=os.getenv("INTENT_PKL") or ""
  if not p: raise RuntimeError("INTENT_PKL not set")
  load_pipeline(p)
  proba, classes = predict_proba_batch(["請問退款流程？","我要申訴","請報價"])
  out.update({"ok":True,"meta":meta(),"shape":getattr(proba,"shape",None),"classes":classes,"row0_max":float(proba[0].max())})
except Exception as e:
  out.update({"ok":False,"error":{"type":type(e).__name__,"msg":str(e)}})
print(json.dumps(out, ensure_ascii=False, indent=2))
PY

# clean port & run server
set +e; pkill -f "uvicorn .*:${PORT}" 2>/dev/null; (command -v fuser >/dev/null && fuser -k "${PORT}/tcp") || true; set -e
log "[RUN] uvicorn $APP --host $HOST --port $PORT"
uvicorn "$APP" --host "$HOST" --port "$PORT" --log-level warning >"$OUT/uvicorn.out" 2>"$OUT/uvicorn.err" & echo $! > "$OUT/uvicorn.pid"

# wait readiness
for i in $(seq 1 25); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://${HOST}:${PORT}/readyz" || true)"
  [ "$code" = "200" ] && break
  sleep 1
done
log "[READY] /readyz code=${code:-NA}"

# HTTP dumps（KIE 先 GET，錯誤再 POST）
dump readyz        "http://$HOST:$PORT/readyz"
dump debug_models  "http://$HOST:$PORT/debug/models"
dump intent        -H 'Content-Type: application/json' -d '{"text":"請問退款流程？"}' "http://$HOST:$PORT/v1/predict/intent"
dump spam          -H 'Content-Type: application/json' -d '{"text":"Win a FREE PRIZE!!!"}' "http://$HOST:$PORT/v1/predict/spam"
dump kie           "http://$HOST:$PORT/v1/kie/health"
KIE_CODE="$(cat "$OUT/kie.code" 2>/dev/null || echo NA)"
if [ "$KIE_CODE" = "405" ] || [ "$KIE_CODE" = "404" ] || [ "$KIE_CODE" = "400" ]; then
  dump kie -H 'Content-Type: application/json' -d '{"text":"dummy"}' "http://$HOST:$PORT/v1/kie/health"
fi

# teardown
kill "$(cat "$OUT/uvicorn.pid" 2>/dev/null || echo)" 2>/dev/null || true
sleep 0.3

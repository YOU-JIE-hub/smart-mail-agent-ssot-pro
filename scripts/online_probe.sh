#!/usr/bin/env bash
set -Eeuo pipefail; umask 022

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-18080}"
APP="${APP:-sma.api.service_compat:app}"
LOG_LEVEL="${LOG_LEVEL:-warning}"
UVICORN_BIN="${UVICORN_BIN:-}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/online/$TS"
mkdir -p "$OUT"; ln -sfn "$OUT" reports_auto/online/latest

log(){ echo "[$(date -Iseconds)] $*" | tee -a "$OUT/run.log"; }
finish(){
  rc=$?
  # 收尾資訊
  echo "readyz          $(cat "$OUT/readyz.code" 2>/dev/null || echo NA)" | tee -a "$OUT/run.log"
  echo "debug_models    $(cat "$OUT/debug_models.code" 2>/dev/null || echo NA)" | tee -a "$OUT/run.log"
  echo "intent          $(cat "$OUT/intent.code" 2>/dev/null || echo NA)" | tee -a "$OUT/run.log"
  echo "spam            $(cat "$OUT/spam.code" 2>/dev/null || echo NA)" | tee -a "$OUT/run.log"
  echo "kie             $(cat "$OUT/kie.code" 2>/dev/null || echo NA)" | tee -a "$OUT/run.log"
  log "EXIT rc=$rc"
  echo "$OUT"
}
trap finish EXIT

# 0) venv + PYTHONPATH
if [ -f .venv/bin/activate ]; then . .venv/bin/activate || true; fi
export PYTHONNOUSERSITE=1
case ":${PYTHONPATH:-}:" in
  *":src:"*) :;;
  *) export PYTHONPATH="src:${PYTHONPATH:-}";;
esac

# 0.1) import 檢查（永遠落檔）
python - <<'PY' >"$OUT/import_check.json" || true
import json,traceback,importlib
res={}
try:
    m = importlib.import_module("sma.api.service_compat")
    res["service_compat"]=getattr(m,"__file__",None); res["status"]="ok"
except Exception as e:
    res={"status":"error","type":type(e).__name__,"message":str(e),"tb":traceback.format_exc()}
print(json.dumps(res,ensure_ascii=False,indent=2))
PY

# 0.2) 若 import 失敗，直接標記 000 並退出（讓你有證據可看）
if jq -e '.status=="error"' "$OUT/import_check.json" >/dev/null 2>&1; then
  for x in readyz debug_models intent spam kie; do echo 000 >"$OUT/$x.code"; done
  printf "ImportError: see %s\n" "$OUT/import_check.json" > "$OUT/SUMMARY.txt"
  exit 0
fi

# 1) 決定 uvicorn 執行檔
if [ -z "$UVICORN_BIN" ]; then
  if command -v uvicorn >/dev/null 2>&1; then UVICORN_BIN="$(command -v uvicorn)"; else UVICORN_BIN="python -m uvicorn"; fi
fi

# 2) 先嘗試現有服務是否已在跑
curl -s -o /dev/null -m 0.5 "http://$HOST:$PORT/readyz" && ALREADY=1 || ALREADY=0

# 3) 若沒在跑，啟一個
API_PID=""
if [ "$ALREADY" = "0" ]; then
  log "Starting API: $UVICORN_BIN $APP --host $HOST --port $PORT --log-level $LOG_LEVEL"
  bash -lc "$UVICORN_BIN $APP --host $HOST --port $PORT --log-level $LOG_LEVEL >'$OUT/uvicorn.out' 2>'$OUT/uvicorn.err' & echo \$! >'$OUT/uvicorn.pid'"
  API_PID="$(cat "$OUT/uvicorn.pid" 2>/dev/null || true)"
  # 等待 readyz
  for i in $(seq 1 40); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://$HOST:$PORT/readyz" || true)"
    [ "$code" = "200" ] && break
    sleep 0.3
  done
fi

# 4) 探測並落檔（headers/body/code）
dump(){
  local name="$1"; shift
  local url="$1"
  local data="$2"
  if [ -n "$data" ]; then
    curl -s -D "$OUT/${name}.hdr" -o "$OUT/${name}.body" -w '%{http_code}' -H 'Content-Type: application/json' \
         -X POST --data "$data" "$url" >"$OUT/${name}.code" || echo 000 >"$OUT/${name}.code"
  else
    curl -s -D "$OUT/${name}.hdr" -o "$OUT/${name}.body" -w '%{http_code}' "$url" >"$OUT/${name}.code" || echo 000 >"$OUT/${name}.code"
  fi
}

dump readyz        "http://$HOST:$PORT/readyz"
dump debug_models  "http://$HOST:$PORT/debug/models"
dump intent        "http://$HOST:$PORT/v1/predict/intent" '{"text":"請問退款流程？"}'
dump spam          "http://$HOST:$PORT/v1/predict/spam"   '{"text":"Win a FREE PRIZE!!!"}'
dump kie           "http://$HOST:$PORT/v1/kie"            '{"text":"發票 AA123456 日期 2024/11/02 金額 NT$12,500"}'

# 5) 若是我啟的進程，收掉並保留 log
if [ -n "$API_PID" ]; then
  kill "$API_PID" 2>/dev/null || true
  sleep 0.2
fi

# 6) SUMMARY
{
  echo "# OUT: $OUT"
  for x in readyz debug_models intent spam kie; do
    printf "%-14s %s\n" "$x" "$(cat "$OUT/$x.code" 2>/dev/null || echo NA)"
  done
  if [ -s "$OUT/uvicorn.err" ]; then
    echo; echo "---- uvicorn.err (tail) ----"; tail -n 60 "$OUT/uvicorn.err"
  fi
} | tee "$OUT/SUMMARY.txt"


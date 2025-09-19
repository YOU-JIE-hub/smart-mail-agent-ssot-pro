#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace

ROOT="${ROOT:-$PWD}"; cd "$ROOT"
mkdir -p reports_auto/ERR reports_auto/api scripts
TS="$(date +%Y%m%dT%H%M%S)"
RUN="reports_auto/api/${TS}"; mkdir -p "$RUN"
OUT="$RUN/api.out"; ERR="$RUN/api.err"; PID="$RUN/api.pid"; SMOKE="$RUN/smoke.txt"
CRASH="reports_auto/ERR/CRASH_${TS}"; mkdir -p "$CRASH"
: >"$OUT"; : >"$ERR"; : >"$SMOKE"

# 0) 固化環境（照你機器上的實際路徑；要換只改這裡）
: > scripts/env.default
cat > scripts/env.default <<'ENV'
PYTHONNOUSERSITE=1
PYTHONPATH=$PWD:src:${PYTHONPATH:-}
SMA_RULES_SRC=/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/.sma_tools/runtime_threshold_router.py
SMA_INTENT_ML_PKL=/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/artifacts/intent_pro_cal.pkl
SMA_LLM_PROVIDER=none
ENV

# 1) 讀環境 + 清埠
# shellcheck disable=SC1091
. scripts/env.default
fuser -k -n tcp 8088 2>/dev/null || true

# 2) 背景啟動（以模組，避免相對匯入問題），所有輸出落檔
nohup bash -lc 'source scripts/env.default; export PYTHONFAULTHANDLER=1 PYTHONUNBUFFERED=1; exec python -u -m tools.api_server' \
  >>"$OUT" 2>>"$ERR" & echo $! > "$PID"

# 3) 探活（POST /classify）；失敗→打包崩潰證據並退出 87
python - <<PY || {
  import json,time,urllib.request,sys
  base="http://127.0.0.1:8088"
  ok=False
  for _ in range(60):
      try:
          r=urllib.request.Request(base+"/classify",
              data=json.dumps({"texts":["ping"],"route":"rule"}).encode(),
              headers={"Content-Type":"application/json"})
          urllib.request.urlopen(r,timeout=1).read()
          ok=True; break
      except Exception:
          time.sleep(0.5)
  sys.exit(0 if ok else 1)
PY

if ! ss -ltnp | grep -q ':8088\b'; then
  env | sort > "$CRASH/env.txt" || true
  ss -ltnp > "$CRASH/ports.txt" 2>&1 || true
  ps -ef | grep -E 'tools\.api_server|python' | grep -v grep > "$CRASH/ps.txt" || true
  cp -f "$OUT" "$CRASH/api.out" 2>/dev/null || true
  cp -f "$ERR" "$CRASH/api.err" 2>/dev/null || true
  [ -f "$PID" ] && cp -f "$PID" "$CRASH/api.pid" || true
  {
    echo "When   : $TS"
    echo "CWD    : $PWD"
    echo "CMD    : python -m tools.api_server"
    echo "PID    : \$(cat "$PID" 2>/dev/null || echo NA)"
    echo; echo "== api.out (tail) =="; tail -n 120 "$OUT" 2>/dev/null || true
    echo; echo "== api.err (tail) =="; tail -n 120 "$ERR" 2>/dev/null || true
    echo; echo "== ports(ss) ==";     tail -n 120 "$CRASH/ports.txt" 2>/dev/null || true
  } > "$CRASH/CRASH_SUMMARY.txt"
  ln -sfn "\$(readlink -f "$CRASH")" reports_auto/ERR/LATEST_CRASH || true
  echo "[CRASH] \$(readlink -f "$CRASH/CRASH_SUMMARY.txt")"
  exit 87
fi

# 4) 成功 → 三端點煙測（全部落檔）
{
  echo "[RULE]"
  curl -s -X POST http://127.0.0.1:8088/classify -H 'Content-Type: application/json' \
    -d '{"texts":["請幫我報價 120000 元，數量 3 台，單號 AB-99127"],"route":"rule"}'
  echo; echo "[ML]"
  curl -s -X POST http://127.0.0.1:8088/classify -H 'Content-Type: application/json' \
    -d '{"texts":["請幫我報價 120000 元，數量 3 台，單號 AB-99127"],"route":"ml"}'
  echo; echo "[KIE]"
  curl -s -X POST http://127.0.0.1:8088/extract -H 'Content-Type: application/json' \
    -d '{"text":"請幫我報價 120000 元，數量 3 台，單號 AB-99127"}'
  echo
} | tee -a "$SMOKE" >/dev/null

ln -sfn "\$(readlink -f "$RUN")" reports_auto/api/LATEST || true
echo "[OK] logs in \$(readlink -f "$RUN")"
echo "[OK] pid=\$(cat "$PID" 2>/dev/null || echo NA)"
echo "[OK] tail api.err:"; tail -n 20 "$ERR" 2>/dev/null || true

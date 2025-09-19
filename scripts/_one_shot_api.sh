#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace

ROOT="${ROOT:-$PWD}"; cd "$ROOT"
mkdir -p reports_auto/ERR reports_auto/api scripts
TS="$(date +%Y%m%dT%H%M%S)"
RUN="reports_auto/api/${TS}"; mkdir -p "$RUN"
OUT="$RUN/api.out"; ERR="$RUN/api.err"; PID="$RUN/api.pid"; SMOKE="$RUN/smoke.txt"
CRASH="reports_auto/ERR/CRASH_${TS}"; mkdir -p "$CRASH"
: >"$OUT"; : >"$ERR"; : >"$SMOKE"

# 0) 固化環境（依你的實際路徑）
: > scripts/env.default
cat > scripts/env.default <<'ENV'
PYTHONNOUSERSITE=1
PYTHONPATH=$PWD:src:${PYTHONPATH:-}
SMA_RULES_SRC=/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/.sma_tools/runtime_threshold_router.py
SMA_INTENT_ML_PKL=/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/artifacts/intent_pro_cal.pkl
SMA_LLM_PROVIDER=none
ENV
# shellcheck disable=SC1091
. scripts/env.default

# 1) 清埠（避免 Address already in use）
fuser -k -n tcp 8088 2>/dev/null || true

# 2) 背景啟動（以模組執行；開 faulthandler；全部落檔）
nohup bash -lc 'source scripts/env.default; export PYTHONFAULTHANDLER=1 PYTHONUNBUFFERED=1; exec python -u -m tools.api_server' \
  >>"$OUT" 2>>"$ERR" & echo $! > "$PID"

# 3) 探活（POST /classify）— 最多 60 次 * 0.5s
python - <<'PY' || exit 97
import json,time,urllib.request,sys
base="http://127.0.0.1:8088"
for _ in range(60):
    try:
        req=urllib.request.Request(base+"/classify",
            data=json.dumps({"texts":["ping"],"route":"rule"}).encode(),
            headers={"Content-Type":"application/json"})
        urllib.request.urlopen(req,timeout=1).read()
        sys.exit(0)
    except Exception:
        time.sleep(0.5)
print("NOT_READY"); sys.exit(1)
PY

# 4) 三端點煙測（落檔）
{
  echo "[RULE]"
  curl -s -X POST http://127.0.0.1:8088/classify -H 'Content-Type: application/json' \
       -d '{"texts":["請幫我報價 120000"],"route":"rule"}'
  echo; echo "[ML]"
  curl -s -X POST http://127.0.0.1:8088/classify -H 'Content-Type: application/json' \
       -d '{"texts":["請幫我報價 120000"],"route":"ml"}'
  echo; echo "[KIE]"
  curl -s -X POST http://127.0.0.1:8088/extract -H 'Content-Type: application/json' \
       -d '{"text":"請報價 $120000，聯絡 0912345678"}'
  echo
} | tee -a "$SMOKE" >/dev/null

ln -sfn "$(readlink -f "$RUN")" reports_auto/api/LATEST || true
echo "[OK] logs in $(readlink -f "$RUN")"
exit 0

# --- 失敗收斂（任何非 0 皆進來） ---
trap '' ERR
RC=$? || true
BUNDLE="$CRASH"
env | sort > "$BUNDLE/env.txt" || true
(ss -ltnp || netstat -ltnp) > "$BUNDLE/ports.txt" 2>&1 || true
ps -ef | grep -E 'tools\.api_server|python' | grep -v grep > "$BUNDLE/ps.txt" || true
cp -f "$OUT" "$BUNDLE/api.out" 2>/dev/null || true
cp -f "$ERR" "$BUNDLE/api.err" 2>/dev/null || true
[ -f "$PID" ] && cp -f "$PID" "$BUNDLE/api.pid" || true
{
  echo "When   : $TS"
  echo "CWD    : $ROOT"
  echo "CMD    : python -m tools.api_server"
  echo "RC     : ${RC:-NA}"
  echo "PID    : $(cat "$PID" 2>/dev/null || echo NA)"
  echo; echo "== api.out (tail) =="; tail -n 200 "$OUT" 2>/dev/null || true
  echo; echo "== api.err (tail) =="; tail -n 200 "$ERR" 2>/dev/null || true
  echo; echo "== ports ==";         tail -n 200 "$BUNDLE/ports.txt" 2>/dev/null || true
} > "$BUNDLE/CRASH_SUMMARY.txt"
ln -sfn "$(readlink -f "$BUNDLE")" reports_auto/ERR/LATEST_CRASH || true
echo "[CRASH] $(readlink -f "$BUNDLE/CRASH_SUMMARY.txt")"
exit 87

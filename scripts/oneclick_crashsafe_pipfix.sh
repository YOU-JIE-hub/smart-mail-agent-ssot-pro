#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace

ROOT="${ROOT:-$PWD}"
cd "$ROOT"
mkdir -p reports_auto/ERR reports_auto/api scripts
TS="$(date +%Y%m%dT%H%M%S)"

# 0) 固化環境（用你現有路徑）
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

# 1) 暫時移走 sitecustomize，避免裝依賴時先崩
SC_BAK=""
if [ -f sitecustomize.py ]; then
  SC_BAK="sitecustomize.py.off.$TS"
  mv sitecustomize.py "$SC_BAK"
fi

# 2) venv / pip 自愈
if [ ! -x ".venv/bin/python" ]; then
  /usr/bin/python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate

have_pip() { python -S - <<'PY' >/dev/null 2>&1 || exit 1
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec("pip") else 1)
PY
}

if ! have_pip; then
  python -S -m ensurepip --upgrade >/dev/null 2>&1 || true
fi
if ! have_pip; then
  /usr/bin/python3 -m venv .venv --upgrade-deps || true
  . .venv/bin/activate
fi
if ! have_pip; then
  BUNDLE="reports_auto/ERR/CRASH_${TS}"; mkdir -p "$BUNDLE"
  env | sort > "$BUNDLE/env.txt"
  echo "pip missing in venv after ensurepip/upgrade-deps" > "$BUNDLE/api.err"
  echo "[CRASH] $BUNDLE/CRASH_SUMMARY.txt"
  {
    echo "When: $TS"
    echo "Msg : pip missing"
  } > "$BUNDLE/CRASH_SUMMARY.txt"
  exit 87
fi

# 3) 安裝最小依賴（純標準輸出，不靜默）
python -S -m pip install --upgrade pip setuptools wheel
python -S -m pip install numpy joblib scikit-learn

# 復位 sitecustomize
[ -n "$SC_BAK" ] && mv "$SC_BAK" sitecustomize.py || true

# 4) 清埠/建 run 目錄
fuser -k -n tcp 8088 2>/dev/null || true
RUN="reports_auto/api/${TS}"; mkdir -p "$RUN"
OUT="$RUN/api.out"; ERR="$RUN/api.err"; PID="$RUN/api.pid"
: >"$OUT"; : >"$ERR"

# 5) 背景啟動（以模組，避免 from tools.* 匯入問題）
nohup bash -lc 'source scripts/env.default; python -m tools.api_server' >>"$OUT" 2>>"$ERR" & echo $! > "$PID"

# 6) 探活（POST /classify），失敗就收斂 CRASH 包
python - <<PY || {
  echo "[FATAL] API not ready. Collecting crash bundle..."
  BUNDLE="reports_auto/ERR/CRASH_${TS}"; mkdir -p "$BUNDLE"
  env | sort > "$BUNDLE/env.txt" || true
  ss -ltnp > "$BUNDLE/ports.txt" 2>&1 || true
  ps -ef | grep -E 'tools\.api_server|python' | grep -v grep > "$BUNDLE/ps.txt" || true
  cp -f "$OUT" "$BUNDLE/api.out" 2>/dev/null || true
  cp -f "$ERR" "$BUNDLE/api.err" 2>/dev/null || true
  [ -f "$PID" ] && cp -f "$PID" "$BUNDLE/api.pid" || true
  {
    echo "When   : $TS"
    echo "CWD    : $ROOT"
    echo "CMD    : python -m tools.api_server"
    echo "PID    : $(cat "$PID" 2>/dev/null || echo NA)"
    echo; echo "== api.out (tail) =="; tail -n 120 "$OUT" 2>/dev/null || true
    echo; echo "== api.err (tail) =="; tail -n 120 "$ERR" 2>/dev/null || true
    echo; echo "== ports(ss) ==";     tail -n 120 "$BUNDLE/ports.txt" 2>/dev/null || true
  } > "$BUNDLE/CRASH_SUMMARY.txt"
  echo "[CRASH] $BUNDLE/CRASH_SUMMARY.txt"
  if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$BUNDLE")" || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$BUNDLE" || true
  fi
  exit 87
}
import json, time, urllib.request, sys
base="http://127.0.0.1:8088"
for i in range(60):
    try:
        r=urllib.request.Request(base+"/classify",
            data=json.dumps({"texts":["ping"],"route":"rule"}).encode(),
            headers={"Content-Type":"application/json"})
        urllib.request.urlopen(r,timeout=1).read()
        print("[READY] API listening @ 8088")
        sys.exit(0)
    except Exception:
        time.sleep(0.5)
print("[FATAL] API not ready after 30s"); sys.exit(1)
PY

# 7) 三端點煙測（存檔）
SMOKE="$RUN/smoke.txt"; : >"$SMOKE"
{
  echo "[RULE]";  curl -s -X POST http://127.0.0.1:8088/classify -H 'Content-Type: application/json' -d '{"texts":["請幫我報價 120000"],"route":"rule"}'
  echo; echo "[ML]";  curl -s -X POST http://127.0.0.1:8088/classify -H 'Content-Type: application/json' -d '{"texts":["請幫我報價 120000"],"route":"ml"}'
  echo; echo "[KIE]"; curl -s -X POST http://127.0.0.1:8088/extract  -H 'Content-Type: application/json' -d '{"text":"請報價 $120000，聯絡 0912345678"}'
  echo
} | tee -a "$SMOKE"

echo "[OK] logs in $RUN"
if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$RUN")" || true
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$RUN" || true
fi

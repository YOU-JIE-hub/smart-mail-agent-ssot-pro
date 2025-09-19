#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace

ROOT="${ROOT:-$PWD}"
cd "$ROOT"
mkdir -p reports_auto/ERR reports_auto/api scripts
TS="$(date +%Y%m%dT%H%M%S)"
RUN="reports_auto/api/${TS}"
OUT="$RUN/api.out"; ERR="$RUN/api.err"; PID="$RUN/api.pid"; SMOKE="$RUN/smoke.txt"
BUNDLE="reports_auto/ERR/CRASH_${TS}"

# --- 固化環境（可依需求調整實際路徑）---
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

# --- 依賴（若 venv 有 pip 才安裝；沒有就略過並記錄）---
have_pip() { python -S - <<'PY' >/dev/null 2>&1 || exit 1
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec("pip") else 1)
PY
}
if have_pip; then
  python -S -m pip install --upgrade --disable-pip-version-check pip setuptools wheel >/dev/null 2>&1 || true
  python -S -m pip install --disable-pip-version-check -q numpy joblib scikit-learn || true
else
  echo "[WARN] pip not found in venv; skip deps install" >&2
fi

# --- 清埠 + 準備 run 目錄 ---
fuser -k -n tcp 8088 2>/dev/null || true
mkdir -p "$RUN"
: >"$OUT"; : >"$ERR"; : >"$SMOKE"
ln -snf "$RUN" reports_auto/api/LAST_TRY

# --- 背景啟動（以模組）---
nohup bash -lc 'source scripts/env.default; export PYTHONFAULTHANDLER=1 PYTHONUNBUFFERED=1; exec python -u -m tools.api_server' \
  >>"$OUT" 2>>"$ERR" & echo $! > "$PID"
sleep 0.3

# --- 探活（POST /classify / rule）---
python - <<'PY' || exit 99
import json,time,urllib.request,sys
base="http://127.0.0.1:8088"
for i in range(60):
    try:
        r=urllib.request.Request(base+"/classify",
            data=json.dumps({"texts":["ping"],"route":"rule"}).encode(),
            headers={"Content-Type":"application/json"})
        urllib.request.urlopen(r,timeout=1).read()
        print("[READY] API @ 8088"); sys.exit(0)
    except Exception:
        time.sleep(0.5)
print("[FATAL] API not ready after 30s"); sys.exit(1)
PY

rc=$?
if [ $rc -ne 0 ]; then
  mkdir -p "$BUNDLE"
  env | sort > "$BUNDLE/env.txt" || true
  ss -ltnp > "$BUNDLE/ports.txt" 2>&1 || true
  ps -ef | grep -E 'python|api_server' | grep -v grep > "$BUNDLE/ps.txt" || true
  cp -f "$OUT" "$BUNDLE/api.out" 2>/dev/null || true
  cp -f "$ERR" "$BUNDLE/api.err" 2>/dev/null || true
  [ -f "$PID" ] && cp -f "$PID" "$BUNDLE/api.pid" || true
  {
    echo "When   : $TS"
    echo "CWD    : $ROOT"
    echo "CMD    : python -m tools.api_server"
    echo "PID    : $(cat "$PID" 2>/dev/null || echo NA)"
    echo; echo "== tail api.out =="; tail -n 120 "$OUT" 2>/dev/null || true
    echo; echo "== tail api.err =="; tail -n 120 "$ERR" 2>/dev/null || true
    echo; echo "== ss -ltnp ==";     tail -n 120 "$BUNDLE/ports.txt" 2>/dev/null || true
  } > "$BUNDLE/CRASH_SUMMARY.txt"
  ln -snf "$BUNDLE" reports_auto/ERR/LATEST_CRASH
  echo "[CRASH] reports_auto/ERR/LATEST_CRASH/CRASH_SUMMARY.txt"
  if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$BUNDLE")" || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$BUNDLE" || true
  fi
  exit 87
fi

# --- 成功：三端點煙測 + LATEST symlink + 自動開資料夾 ---
ln -snf "$RUN" reports_auto/api/LATEST
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

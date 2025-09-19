#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="${ROOT:-$PWD}"
cd "$ROOT"
mkdir -p reports_auto/api scripts

# 固化環境（可依你實際路徑調整）
: > scripts/env.default
cat > scripts/env.default <<'ENV'
PYTHONNOUSERSITE=1
PYTHONPATH=$PWD:src:${PYTHONPATH:-}
SMA_RULES_SRC=/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/.sma_tools/runtime_threshold_router.py
SMA_INTENT_ML_PKL=/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/artifacts/intent_pro_cal.pkl
SMA_LLM_PROVIDER=none
ENV

# 清埠
fuser -k -n tcp 8088 2>/dev/null || true

TS="$(date +%Y%m%dT%H%M%S)"
RUN="reports_auto/api/${TS}"
mkdir -p "$RUN"
echo "$RUN" > reports_auto/api/LAST_RUN_DIR

# 背景啟動（以模組，避免 from tools.* 匯入問題）
CMD="source scripts/env.default; python -m tools.api_server"
scripts/crash_guard.sh --cmd "$CMD" &  # 讓 crash_guard 自己收斂崩潰

# 探活（最多 60 次，每 0.5s）
python - <<'PY' || {
  echo "[NOT_READY] see crash bundle: $(cat reports_auto/ERR/LATEST_CRASH 2>/dev/null || echo NA)"
  exit 87
}
import json,time,urllib.request,sys
base="http://127.0.0.1:8088"
for i in range(60):
    try:
        req=urllib.request.Request(base+"/classify",
            data=json.dumps({"texts":["ping"],"route":"rule"}).encode(),
            headers={"Content-Type":"application/json"})
        urllib.request.urlopen(req,timeout=1).read()
        print("[READY] API @ 8088"); sys.exit(0)
    except Exception:
        time.sleep(0.5)
print("[FATAL] API not ready after 30s"); sys.exit(1)
PY

# 成功：留快照、建立 LATEST
OUT="$RUN/api.out"; ERR="$RUN/api.err"
[ -f reports_auto/ERR/LATEST_CRASH ] && rm -f reports_auto/ERR/LATEST_CRASH || true
ln -snf "$RUN" reports_auto/api/LATEST

# 煙測三端點，落到 smoke.txt
SMOKE="$RUN/smoke.txt"; : >"$SMOKE"
{
  echo "[RULE]";  curl -s -X POST http://127.0.0.1:8088/classify -H 'Content-Type: application/json' -d '{"texts":["請幫我報價 120000"],"route":"rule"}'
  echo; echo "[ML]";  curl -s -X POST http://127.0.0.1:8088/classify -H 'Content-Type: application/json' -d '{"texts":["請幫我報價 120000"],"route":"ml"}'
  echo; echo "[KIE]"; curl -s -X POST http://127.0.0.1:8088/extract  -H 'Content-Type: application/json' -d '{"text":"請報價 $120000，聯絡 0912345678"}'
  echo
} | tee -a "$SMOKE"

# 自動開資料夾（看得到檔案，不用再靠終端輸出）
if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$RUN")" || true
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$RUN" || true
fi
echo "[OK] logs in $RUN"

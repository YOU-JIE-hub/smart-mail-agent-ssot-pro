#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace; set +m; umask 022

ROOT="$PWD"
mkdir -p reports_auto/ERR reports_auto/api scripts
TS="$(date +%Y%m%dT%H%M%S)"
RUN="reports_auto/api/${TS}"; CRASH="reports_auto/ERR/CRASH_${TS}"
mkdir -p "$RUN" "$CRASH"
OUT="$RUN/api.out"; ERRF="$RUN/api.err"; PID="$RUN/api.pid"; SMOKE="$RUN/smoke.txt"
: >"$OUT"; : >"$ERRF"; : >"$SMOKE"

# 0) 固化環境（只需改這 5 行）
cat > scripts/env.default <<'ENV'
PYTHONNOUSERSITE=1
PYTHONPATH=$PWD:src:${PYTHONPATH:-}
SMA_RULES_SRC=/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/.sma_tools/runtime_threshold_router.py
SMA_INTENT_ML_PKL=/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/artifacts/intent_pro_cal.pkl
SMA_LLM_PROVIDER=none
ENV

# 1) 預收集系統線索（即使秒退也留得到）
env | sort > "$CRASH/env.pre.txt" || true
ulimit -a   > "$CRASH/ulimit.txt" 2>&1 || true
cat /proc/meminfo > "$CRASH/meminfo.pre.txt" 2>/dev/null || true
dmesg -T | tail -n 200 > "$CRASH/dmesg.pre.txt" 2>/dev/null || true

# 2) 寫入啟動注入器：只覆寫 classify_rule / extract_slots_rule（不改 ML）
cat > scripts/launcher_rule_override.py <<'PY2'
#!/usr/bin/env python3
import os, sys, importlib.util, types, re, runpy
ROOT = os.getcwd()

# 載入原版 pipeline
orig_path = os.path.join(ROOT, "tools", "pipeline_baseline.py")
spec = importlib.util.spec_from_file_location("tools.pipeline_baseline.__orig", orig_path)
orig = importlib.util.module_from_spec(spec); spec.loader.exec_module(orig)

# 包裝一份，預設繼承全部
wrap = types.ModuleType("tools.pipeline_baseline")
wrap.__dict__.update(orig.__dict__)

# 讀 runtime 規則（可選）
predict = None
rules = os.environ.get("SMA_RULES_SRC", "")
if rules and os.path.isfile(rules):
    try:
        rspec = importlib.util.spec_from_file_location("sma_runtime_rules", rules)
        rm = importlib.util.module_from_spec(rspec); rspec.loader.exec_module(rm)
        if hasattr(rm, "predict_one"): predict = rm.predict_one
        elif hasattr(rm, "predict"):    predict = lambda t: (rm.predict([t]) or ["other"])[0]
    except Exception:
        predict = None

def classify_rule(email, contract, **kw):
    text = email.get("text","") if isinstance(email, dict) else (email or "")
    if predict:
        return predict(text) or "other"
    return orig.classify_rule(email=email, contract=contract, **kw)

def extract_slots_rule(email, intent, **kw):
    txt = email.get("text","") if isinstance(email, dict) else (email or "")
    s = {"price": None, "qty": None, "id": None}
    m = (re.search(r'(?:\$|NTD?\s*)([0-9][\d,\.]*)', txt, re.I) or
         re.search(r'([0-9][\d,\.]*)\s*(?:元|NTD?|\$)', txt, re.I))
    if m:
        v = m.group(1).replace(",", "")
        try: s["price"] = float(v)
        except: s["price"] = v
    m = re.search(r'(?:數量|各|共|x)\s*([0-9]+)', txt, re.I)
    if m:
        try: s["qty"] = int(m.group(1))
        except: s["qty"] = m.group(1)
    m = re.search(r'\b([A-Z]{2,}-?\d{4,})\b', txt)
    if m: s["id"] = m.group(1)
    return s

wrap.classify_rule = classify_rule
wrap.extract_slots_rule = extract_slots_rule
sys.modules["tools.pipeline_baseline"] = wrap

# 進入原本 API server
runpy.run_module("tools.api_server", run_name="__main__")
PY2
chmod +x scripts/launcher_rule_override.py

# 3) 讀環境 + 清埠
. scripts/env.default
fuser -k -n tcp 8088 2>/dev/null || true

# 4) 啟動（全輸出落檔；不輸出 job 提示）
nohup env PYTHONFAULTHANDLER=1 PYTHONUNBUFFERED=1 \
  python -u scripts/launcher_rule_override.py >>"$OUT" 2>>"$ERRF" & echo $! > "$PID"

# 5) 健檢
python - <<'PY3' || true
import json,time,urllib.request,sys
base="http://127.0.0.1:8088"; ok=False
for _ in range(60):
    try:
        req=urllib.request.Request(base+"/classify",
              data=json.dumps({"texts":["ping"],"route":"rule"}).encode(),
              headers={"Content-Type":"application/json"})
        urllib.request.urlopen(req,timeout=1).read()
        ok=True; break
    except Exception: time.sleep(0.5)
print("[READY]" if ok else "[NOT_READY]")
sys.exit(0 if ok else 1)
PY3

# 6) 成敗分支
if ss -ltnp 2>/dev/null | grep -q ':8088\b'; then
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
  ln -sfn "$(readlink -f "$RUN")" reports_auto/api/LATEST || true
  echo "[OK] logs in $(readlink -f "$RUN")"
  echo "[OK] pid=$(cat "$PID" 2>/dev/null || echo NA)"
  exit 0
else
  env | sort > "$CRASH/env.txt" || true
  ss -ltnp    > "$CRASH/ports.txt" 2>&1 || true
  ps -ef | grep -E 'tools\.api_server|launcher_rule_override|python' | grep -v grep > "$CRASH/ps.txt" || true
  dmesg -T | tail -n 400 > "$CRASH/dmesg.post.txt" 2>/dev/null || true
  cp -f "$OUT" "$CRASH/api.out" 2>/dev/null || true
  cp -f "$ERRF" "$CRASH/api.err" 2>/dev/null || true
  [ -f "$PID" ] && cp -f "$PID" "$CRASH/api.pid" || true

  REASON="unknown"
  grep -qi 'Out of memory|Killed process .* python' "$CRASH/dmesg.post.txt" && REASON="oom-killed"
  grep -qi 'Address already in use' "$CRASH/api.err" && REASON="addr-in-use"
  grep -qi 'ModuleNotFoundError: No module named' "$CRASH/api.err" && REASON="module-missing"
  grep -qi 'ImportError' "$CRASH/api.err" && REASON="import-error"
  grep -qi 'Traceback (most recent call last):' "$CRASH/api.err" && REASON="${REASON},traceback"

  echo "reason=$REASON" > "$CRASH/CRASH_SUMMARY.txt"
  ln -sfn "$(readlink -f "$CRASH")" reports_auto/ERR/LATEST_CRASH || true
  echo "[CRASH] $(readlink -f "$CRASH") (reason=$REASON)"
  exit 87
fi

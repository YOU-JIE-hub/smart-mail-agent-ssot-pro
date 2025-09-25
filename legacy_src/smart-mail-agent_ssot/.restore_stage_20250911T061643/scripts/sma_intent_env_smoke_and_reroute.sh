#!/usr/bin/env bash
# 修復 sklearn 版本 → 模型冒煙測試 → 挑選有內容的 E2E 目錄 → 重路由並落檔
set -Eeuo pipefail

ROOT="/home/youjie/projects/smart-mail-agent_ssot"
TS="$(date +%Y%m%dT%H%M%S)"
SMOKE_DIR="$ROOT/reports_auto/errors/INTENT_ENV_SMOKE_${TS}"
mkdir -p "$SMOKE_DIR"

log()  { printf '%s\n' "$*" | tee -a "$SMOKE_DIR/smoke.log" >&2; }
fail() { printf '[FATAL] %s\n' "$*" | tee -a "$SMOKE_DIR/smoke.log" >&2; exit 2; }

cd "$ROOT"

# 1) 釘版本（與 1.7.1 相容的常見組合；Python 3.10）
log "[INFO] fixing sklearn stack to 1.7.1"
python - <<'PY' 2>&1 | tee -a reports_auto/errors/INTENT_ENV_SMOKE_'"$TS"'/pip_fix.log
import sys, subprocess
pkgs = [
    "pip>=24.0", "setuptools>=70.0.0", "wheel>=0.43.0",
    "numpy==1.26.4", "scipy==1.13.1", "threadpoolctl==3.5.0",
    "joblib==1.4.2", "scikit-learn==1.7.1"
]
subprocess.check_call([sys.executable, "-m", "pip", "install", "-U"] + pkgs)
import sklearn, joblib, numpy, scipy, threadpoolctl
print("sklearn=", sklearn.__version__)
print("joblib=", joblib.__version__)
print("numpy=", numpy.__version__)
print("scipy=", scipy.__version__)
PY

# 2) 模型冒煙測試
log "[INFO] smoke-testing artifacts/intent_pro_cal.pkl"
python - <<'PY' 2>&1 | tee -a reports_auto/errors/INTENT_ENV_SMOKE_'"$TS"'/smoke_test.log
import sys, json, numpy as np
from pathlib import Path
import joblib, traceback

ROOT=Path("/home/youjie/projects/smart-mail-agent_ssot")
ERR=ROOT/"reports_auto/errors/INTENT_ENV_SMOKE_${TS}"
(ERR).mkdir(parents=True, exist_ok=True)

# 確保 __main__.rules_feat 存在
try:
    import __main__
    from smart_mail_agent.ml.rules_feat import rules_feat as _rf
    setattr(__main__, "rules_feat", _rf)
except Exception:
    pass

model_p=ROOT/"artifacts/intent_pro_cal.pkl"
if not model_p.exists():
    print("[FATAL] missing model:", model_p); sys.exit(3)

try:
    clf=joblib.load(model_p)
except Exception:
    import pickle
    with open(model_p,"rb") as f:
        clf=pickle.load(f)

texts=[
    "您好，請提供年度合約報價與SLA選項",
    "App 無法登入，顯示 500 錯誤，請協助排除",
    "客訴：上週出貨延遲造成退單，請處理賠償"
]
ok=False
mode="none"
try:
    if hasattr(clf,"predict_proba"):
        P=clf.predict_proba(texts)
        ok=True; mode="predict_proba"
        print("classes=", getattr(clf,"classes_",None))
        print("proba_shape=", getattr(P,"shape",None))
    else:
        y=clf.predict(texts)
        ok=True; mode="predict"
        print("pred=", list(y))
except Exception as e:
    print("[EXC]", repr(e))
    traceback.print_exc()

print("SMOKE_OK=", ok, "MODE=", mode)
sys.exit(0 if ok else 4)
PY
SMOKE_RC=$? || true

# 3) 選擇有內容的 E2E 目錄
pick_run_dir() {
  base="$ROOT/reports_auto/e2e_mail"
  [ -d "$base" ] || { echo ""; return; }
  mapfile -t dirs < <(find "$base" -maxdepth 1 -type d -regex '.*/[0-9]{8}T[0-9]{6}$' -printf "%T@ %p\n" | sort -nr | awk '{print $2}')
  for d in "${dirs[@]}"; do
    f="$d/cases.jsonl"
    [ -f "$f" ] || continue
    # 有 text/subject/body 任一關鍵鍵值即視為可路由文本
    if grep -E '"(text|subject|body)"\s*:' -q "$f"; then
      echo "$d"; return
    fi
    # 若行數非 0，但沒有文本，就先記為候選
    nb=$(grep -cve '^\s*$' "$f" || true)
    if [ "${nb:-0}" -gt 0 ]; then cand="$d"; fi
  done
  if [ -n "${cand:-}" ]; then echo "$cand"; return; fi
  echo ""
}

RUN_DIR="$(pick_run_dir || true)"
# 保底用你已確認有內容的資料夾
[ -z "${RUN_DIR:-}" ] && RUN_DIR="$ROOT/reports_auto/e2e_mail/20250902T144500"
[ -d "$RUN_DIR" ] || fail "no usable e2e run dir found"

log "[INFO] using run_dir=$RUN_DIR"

# 4) 執行重路由（即使 SMOKE 失敗也可；腳本內會規則退化並落檔）
python scripts/sma_reroute_last_run_intent.py --run-dir "$RUN_DIR" 2>&1 | tee -a "$SMOKE_DIR/reroute.log" || true

# 5) 指標與產物路徑回報
echo "[RESULT] run_dir=$RUN_DIR"
for f in intent_reroute_summary.md intent_reroute_audit.csv intent_reroute_suggestion.ndjson; do
  if [ -f "$RUN_DIR/$f" ]; then
    echo "[OK] $f -> $RUN_DIR/$f"
  else
    echo "[MISS] $f"
  fi
done
echo "[LOG] smoke suite -> $SMOKE_DIR"

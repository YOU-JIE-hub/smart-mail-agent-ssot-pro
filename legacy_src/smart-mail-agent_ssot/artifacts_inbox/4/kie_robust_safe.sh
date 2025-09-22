#!/usr/bin/env bash
# kie_robust_safe.sh — 產生擾動集 → 跑預測 → 計算魯棒性；全程不丟檔
set -Eeuo pipefail; set -o errtrace; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$ROOT" || { echo "[FATAL] repo not found: $ROOT"; exit 96; }

BASE_PRED="reports_auto/kie_pred.jsonl"
BASE_SILV="data/kie/silver.jsonl"
BASE_SAVE="reports_auto/kie_pred_base.jsonl"
PERT_SAVE="reports_auto/kie_pred_perturb.jsonl"
ROB_OUT="reports_auto/kie_robust.txt"
TEST_IN="data/intent/test.jsonl"
TEST_PERT="data/intent/test_perturb.jsonl"

# 0) 檢查依賴腳本
[ -x sma_tools/kie_regex_min.sh ] || { echo "[FATAL] missing sma_tools/kie_regex_min.sh"; exit 91; }
[ -f sma_tools/kie_robust_eval.py ] || { echo "[FATAL] missing sma_tools/kie_robust_eval.py"; exit 92; }
[ -f sma_tools/augment_intent_texts.py ] || {
  # 若你沒有 augment 腳本，這裡給最小版：隨機全半形/標點擾動
  cat > sma_tools/augment_intent_texts.py <<'PY'
import argparse, json, random
R=random.Random(42)
def perturb(s):
    t=s.replace("$","＄") if R.random()<0.5 else s
    t=t.replace(",","，") if R.random()<0.5 else t
    t=t.replace(".","．") if R.random()<0.3 else t
    return t
ap=argparse.ArgumentParser(); ap.add_argument("--in_jsonl"); ap.add_argument("--out_jsonl"); ap.add_argument("--ratio",type=float,default=1.0)
a=ap.parse_args()
rows=[json.loads(l) for l in open(a.in_jsonl,encoding="utf-8")]
aug=[{"text":perturb(r["text"]), "label":r.get("label")} for r in rows]
open(a.out_jsonl,"w",encoding="utf-8").write("\n".join(json.dumps(r,ensure_ascii=False) for r in aug)+"\n")
print(f"[AUG] base={len(rows)}  -> {a.out_jsonl}")
PY
}

# 1) 確保有「base 預測」
if [ ! -s "$BASE_PRED" ]; then
  echo "[INFO] base pred missing → 用 $TEST_IN 先跑一版"
  sma_tools/kie_regex_min.sh "$TEST_IN"
fi
[ -s "$BASE_PRED" ] || { echo "[FATAL] still no $BASE_PRED"; exit 93; }

# 2) 備份 base
cp -f "$BASE_PRED" "$BASE_SAVE"
cp -f "$BASE_SILV" "data/kie/silver_base.jsonl" 2>/dev/null || true

# 3) 產擾動集並跑預測（覆蓋到 BASE_PRED）
python sma_tools/augment_intent_texts.py --in_jsonl "$TEST_IN" --out_jsonl "$TEST_PERT" --ratio 1.0
sma_tools/kie_regex_min.sh "$TEST_PERT"

# 此時 reports_auto/kie_pred.jsonl 是「擾動版」→ 先另存
cp -f "$BASE_PRED" "$PERT_SAVE"

# 4) 還原 base
mv -f "$BASE_SAVE" "$BASE_PRED"

# 5) 計算魯棒性
python sma_tools/kie_robust_eval.py \
  --pred_base "$BASE_PRED" \
  --pred_aug  "$PERT_SAVE" \
  --out       "$ROB_OUT"

echo "[OK] ROBUST -> $ROB_OUT"

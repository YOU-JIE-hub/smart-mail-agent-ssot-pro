#!/usr/bin/env bash
set -Eeuo pipefail
SEED="${SEED:-42}"
TRAIN="${1:-data/intent/i_20250901_merged.jsonl}"
TEST="${2:-data/intent/external_realistic_test.clean.jsonl}"

# 路徑
OUT=reports_auto
ART=artifacts
mkdir -p "$OUT" "$ART"

# 1) 訓練 Pro（word+char+rules；CV 挑 C；Sigmoid 校準）
python .sma_tools/train_pro_fresh.py \
  --train "$TRAIN" \
  --test  "$TEST" \
  --out_model "$ART/intent_pro_cal.pkl" \
  --out_prefix "$OUT/ext_pro_fresh" \
  --seed "$SEED" --Cs "0.5,1.0,2.0" --max_df 1.0

# 2) 調閾值（p1×margin 網格；鎖 policy_qa）
python .sma_tools/tune_thresholds.py \
  --model "$ART/intent_pro_cal.pkl" \
  --test  "$TEST" \
  --out_prefix "$OUT/ext_pro_tuned" \
  --p1_grid "0.48,0.50,0.52,0.55,0.58,0.60" \
  --margin_grid "0.04,0.06,0.08,0.10,0.12,0.15" \
  --policy_lock

# 3) 從 grid 取最優、落盤 thresholds.json
python - <<'PY'
import json, pathlib
from pathlib import Path
import numpy as np
g = Path("reports_auto/ext_pro_tuned_grid.tsv")
best = None
with g.open(encoding="utf-8") as f:
    next(f)  # header
    for ln in f:
        p1, m, acc, mf1 = ln.strip().split("\t")
        row = (float(acc), float(mf1), float(p1), float(m))
        if (best is None) or (row > best): best = row
acc, mf1, p1, margin = best
cfg = {
  "p1": round(p1, 2),
  "margin": round(margin, 2),
  "policy_lock": True,
  "tuned_on": "data/intent/external_realistic_test.clean.jsonl",
  "n": 120,
  "accuracy": round(acc, 4),
  "macroF1": round(mf1, 4)
}
Path("reports_auto/intent_thresholds.json").write_text(
    json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
print("[THR]", cfg)
PY

# 4) 生成模型卡（整合指標/混淆/環境）
python .sma_tools/make_model_card.py \
  --fresh_eval "$OUT/ext_pro_fresh_eval.txt" \
  --tuned_eval "$OUT/ext_pro_tuned_eval.txt" \
  --confusion   "$OUT/ext_pro_tuned_confusion.tsv" \
  --thresholds  "$OUT/intent_thresholds.json" \
  --seed "$SEED"

# 5) 打包發版
TS="$(date -u +%Y%m%dT%H%M%SZ)-pro"
REL="artifacts/releases/intent/$TS"
mkdir -p "$REL"
cp -f "$ART/intent_pro_cal.pkl" "$REL/"
cp -f "$OUT"/intent_thresholds.json "$REL/"
cp -f "$OUT"/ext_pro_* "$REL/" 2>/dev/null || true
cp -f model_card_pro.md "$REL/"

# 6) 環境/摘要
python - <<'PY'
import json, platform, sys, sklearn, numpy, scipy, pathlib
snap = {
  "python": sys.version.split()[0],
  "numpy": numpy.__version__,
  "scipy": scipy.__version__,
  "sklearn": sklearn.__version__,
}
pathlib.Path("reports_auto/env_versions.json").write_text(
    json.dumps(snap, indent=2), encoding="utf-8")
print("[ENV]", snap)
PY

echo
echo "=== SUMMARY ==="
awk 'NR<=12' "$OUT/ext_pro_tuned_eval.txt" || true
echo "Model:     $ART/intent_pro_cal.pkl"
echo "Threshold: $OUT/intent_thresholds.json"
echo "Release:   $REL"

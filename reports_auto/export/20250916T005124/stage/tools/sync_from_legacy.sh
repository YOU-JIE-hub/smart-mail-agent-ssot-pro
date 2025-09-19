#!/usr/bin/env bash
set -Eeuo pipefail

SRC_ROOT="${SRC_ROOT:-$HOME/projects/smart-mail-agent_ssot}"
DST_ROOT="${DST_ROOT:-$HOME/projects/smart-mail-agent-ssot-pro}"

cd "$DST_ROOT"

# 基本環境
mkdir -p reports_auto/intent/reports_auto reports_auto/eval reports_auto/actions artifacts artifacts_prod data fixtures
[ -f .venv/bin/activate ] || python3 -m venv .venv
. .venv/bin/activate
pip -q install -U scikit-learn==1.7.1 numpy==2.2.6 scipy joblib pandas || true

echo "[Spam] 檢查權重/門檻/資料"
[ -f artifacts_prod/model_pipeline.pkl ] || { [ -f "$SRC_ROOT/artifacts_prod/model_pipeline.pkl" ] && cp -a "$SRC_ROOT/artifacts_prod/model_pipeline.pkl" artifacts_prod/ && echo "  + copy model_pipeline.pkl"; }
[ -f artifacts_prod/ens_thresholds.json ] || { [ -f "$SRC_ROOT/artifacts_prod/ens_thresholds.json" ] && cp -a "$SRC_ROOT/artifacts_prod/ens_thresholds.json" artifacts_prod/ && echo "  + copy ens_thresholds.json"; }
if [ ! -f data/benchmarks/spamassassin.clean.jsonl ] && [ -f "$SRC_ROOT/data/benchmarks/spamassassin.clean.jsonl" ]; then
  mkdir -p data/benchmarks
  cp -a "$SRC_ROOT/data/benchmarks/spamassassin.clean.jsonl" data/benchmarks/ && echo "  + copy spam dataset"
fi
# quick report：先嘗試沿用舊報告，不在就有腳本才重跑
if [ ! -f reports_auto/prod_quick_report.md ] && [ -f "$SRC_ROOT/reports_auto/prod_quick_report.md" ]; then
  cp -a "$SRC_ROOT/reports_auto/prod_quick_report.md" reports_auto/ && echo "  + copy prod_quick_report.md"
elif [ ! -f reports_auto/prod_quick_report.md ] && [ -f scripts/sma_quick_eval.py ]; then
  python scripts/sma_quick_eval.py \
    --data data/benchmarks/spamassassin.clean.jsonl \
    --model artifacts_prod/model_pipeline.pkl \
    --thresholds artifacts_prod/ens_thresholds.json \
    --out reports_auto/prod_quick_report.md && echo "  + regen prod_quick_report.md"
fi

echo "[Intent] tuned 報告與 thresholds"
mkdir -p reports_auto/intent/reports_auto
for f in ext_pro_tuned_eval.txt ext_pro_tuned_confusion.tsv ext_pro_tuned_grid.tsv; do
  if [ ! -f "reports_auto/intent/reports_auto/$f" ] && [ -f "$SRC_ROOT/reports_auto/intent/reports_auto/$f" ]; then
    cp -a "$SRC_ROOT/reports_auto/intent/reports_auto/$f" reports_auto/intent/reports_auto/ && echo "  + copy $f"
  fi
done
# thresholds：優先用舊專案 bundle 版；新專案根也保留一份方便 E2E
if [ ! -f reports_auto/intent_thresholds.json ]; then
  if [ -f "$SRC_ROOT/reports_auto/intent/reports_auto/intent_thresholds.json" ]; then
    cp -a "$SRC_ROOT/reports_auto/intent/reports_auto/intent_thresholds.json" reports_auto/ && echo "  + copy intent_thresholds.json"
  fi
fi
# 權重：如新專案沒有而舊專案有，做 symlink（可改成 cp -a）
if [ ! -f artifacts/intent_pro_cal.pkl ] && [ -f "$SRC_ROOT/artifacts/intent_pro_cal.pkl" ]; then
  mkdir -p artifacts
  ln -sf "$SRC_ROOT/artifacts/intent_pro_cal.pkl" artifacts/intent_pro_cal.pkl && echo "  + link artifacts/intent_pro_cal.pkl"
fi

echo "[KIE] 權重資料夾與快照"
if [ ! -d reports_auto/kie/kie ] && [ -d "$SRC_ROOT/reports_auto/kie/kie" ]; then
  mkdir -p reports_auto/kie
  cp -a "$SRC_ROOT/reports_auto/kie/kie" reports_auto/kie/ && echo "  + copy reports_auto/kie/kie/"
fi
for f in kie_eval.txt kie_eval_per_label.tsv kie_eval_release_snap.txt; do
  if [ ! -f "reports_auto/$f" ] && [ -f "$SRC_ROOT/reports_auto/$f" ]; then
    cp -a "$SRC_ROOT/reports_auto/$f" reports_auto/ && echo "  + copy reports_auto/$f"
  fi
done
if [ ! -f data/kie/test.jsonl ] && [ -f "$SRC_ROOT/data/kie/test.jsonl" ]; then
  mkdir -p data/kie
  cp -a "$SRC_ROOT/data/kie/test.jsonl" data/kie/ && echo "  + copy data/kie/test.jsonl"
fi

echo "[Intent] 重跑三種評測（若可用）"
[ -f tools/tri_model_eval.py ]            && python tools/tri_model_eval.py            || true
[ -f tools/tri_model_eval_ml.py ]         && python tools/tri_model_eval_ml.py         || true
[ -f tools/tri_model_eval_ml_boosted.py ] && python tools/tri_model_eval_ml_boosted.py || true
[ -f tools/e2e_full_ml_boosted.py ]       && python tools/e2e_full_ml_boosted.py       || true

echo "[Summary] 主要產物存在性"
for p in \
  artifacts_prod/model_pipeline.pkl \
  artifacts_prod/ens_thresholds.json \
  reports_auto/prod_quick_report.md \
  artifacts/intent_pro_cal.pkl \
  reports_auto/intent/reports_auto/ext_pro_tuned_eval.txt \
  reports_auto/intent/reports_auto/ext_pro_tuned_confusion.tsv \
  reports_auto/intent/reports_auto/ext_pro_tuned_grid.tsv \
  reports_auto/intent_thresholds.json \
  reports_auto/kie/kie \
  reports_auto/kie_eval_release_snap.txt \
  reports_auto/kie_eval.txt \
  reports_auto/eval \
  reports_auto/actions ; do
  if [ -e "$p" ]; then echo "  - OK   $p"; else echo "  - MISS $p"; fi
done

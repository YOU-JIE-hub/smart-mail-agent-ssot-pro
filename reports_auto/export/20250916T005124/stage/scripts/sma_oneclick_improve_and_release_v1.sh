#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

echo "[1/6] 產出標註批次（FN/FP -> CSV）"
bash scripts/sma_weekly_dataset_update_v1.sh || true

echo "[2/6] (可選) 合併已標註 CSV 回資料集"
LATEST_CSV="$(ls -t reports_auto/labeling/*/intent_labeling_batch.csv 2>/dev/null | head -n1 || true)"
[ -n "${APPLY_LABELS:-}" ] && [ -f "$LATEST_CSV" ] && bash scripts/sma_merge_labeled_to_dataset_v1.sh "$LATEST_CSV" || echo "[SKIP] 未設定 APPLY_LABELS=1 或找不到 CSV"

echo "[3/6] 訓練 Intent Stacker v1"
bash scripts/sma_train_intent_stacker_v1.sh || true

echo "[4/6] KIE SLA 後處理提昇 + 自評"
bash scripts/sma_kie_post_boost_sla_v1.sh || true

echo "[5/6] 全套評估 + Scorecard"
bash scripts/sma_oneclick_eval_all_pro.sh

echo "[6/6] 打包 Release"
bash scripts/sma_release_bundle_v1.sh
echo "[DONE] improve + release completed."

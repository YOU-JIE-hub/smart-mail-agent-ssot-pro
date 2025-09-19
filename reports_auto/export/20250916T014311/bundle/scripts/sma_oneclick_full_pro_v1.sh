#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
STATUS="reports_auto/status"
mkdir -p "$STATUS"

echo "[STEP] 1) 意圖資料清洗與快照"
bash scripts/sma_dump_intent_dataset_for_review.sh || true
bash scripts/sma_intent_dataset_autofix_v1.sh

echo "[STEP] 2) 意圖 v11c（目前最佳基準，含校準與FN/FP匯出）"
bash scripts/sma_intent_rules_focus_v11c.sh

echo "[STEP] 3) KIE 混合法 v4（維持 SLA=HIL 模式）"
bash scripts/sma_oneclick_kie_hybrid_hotfix_v4.sh

echo "[STEP] 4) Spam 自動校準（若要落盤請在前面加：APPLY=1 ）"
bash scripts/sma_oneclick_spam_autocal_hotfix_v4_fix.sh

echo "[STEP] 5) 總結（最近一次 ONECLICK 摘要尾段）"
LATEST="$(ls -t ${STATUS}/ONECLICK_* 2>/dev/null | head -n1)"
if [ -n "$LATEST" ]; then
  echo ">>> ONECLICK summary tail (${LATEST}):"
  tail -n 120 "$LATEST"
else
  echo "[WARN] 尚未生成 ONECLICK 摘要"
fi

echo "[DONE] full_pro_v1 complete."

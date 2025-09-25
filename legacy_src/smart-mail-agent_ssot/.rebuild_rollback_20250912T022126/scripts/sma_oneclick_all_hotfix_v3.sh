#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

# KIE（若你已經有 v4 腳本就呼叫；沒有就略過）
if [ -f scripts/sma_oneclick_kie_hybrid_hotfix_v4.sh ]; then
  bash scripts/sma_oneclick_kie_hybrid_hotfix_v4.sh || true
fi

# Intent v6（純規則）
bash scripts/sma_oneclick_intent_rules_hotfix_v6.sh || true

# Spam v4（預設吃 artifacts_prod/text_predictions_test.tsv）
bash scripts/sma_oneclick_spam_autocal_hotfix_v4_fix.sh || true

echo ">>> ONECLICK summary (latest status tail):"
LATEST="$(ls -t reports_auto/status/ONECLICK_* 2>/dev/null | head -n1)"
[ -n "$LATEST" ] && { echo "$LATEST"; tail -n 120 "$LATEST"; } || echo "[WARN] 尚未生成 ONECLICK 摘要"

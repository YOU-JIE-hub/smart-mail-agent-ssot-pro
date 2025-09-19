#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

# KIE v4（已存在就用）
if [ -f scripts/sma_oneclick_kie_hybrid_hotfix_v4.sh ]; then
  bash scripts/sma_oneclick_kie_hybrid_hotfix_v4.sh || true
fi

# Intent v5
bash scripts/sma_oneclick_intent_rules_hotfix_v5.sh || true

# Spam v2
bash scripts/sma_oneclick_spam_autocal_hotfix_v2.sh || true

echo ">>> ONECLICK summary:"
LATEST="$(ls -t reports_auto/status/ONECLICK_* 2>/dev/null | head -n1)"
[ -n "$LATEST" ] && { echo "$LATEST"; tail -n 100 "$LATEST"; } || echo "[WARN] 尚未生成 ONECLICK 摘要"

#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

if [ -f scripts/sma_oneclick_kie_hybrid_hotfix_v4.sh ]; then
  bash scripts/sma_oneclick_kie_hybrid_hotfix_v4.sh || true
fi
bash scripts/sma_oneclick_intent_rules_hotfix_v7.sh || true
bash scripts/sma_oneclick_spam_autocal_hotfix_v4_fix.sh || true

echo ">>> ONECLICK summary (latest status tail):"
LATEST="$(ls -t reports_auto/status/ONECLICK_* 2>/dev/null | head -n1)"
[ -n "$LATEST" ] && { echo "$LATEST"; tail -n 140 "$LATEST"; } || echo "[WARN] 尚未生成 ONECLICK 摘要"

#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1
bash scripts/sma_oneclick_eval_all_pro.sh
SCORECARD="$(ls -t reports_auto/status/SCORECARD_* 2>/dev/null | head -n1)"
echo "[OK] scorecard => ${SCORECARD}"
if [ -n "${SLACK_WEBHOOK:-}" ] && [ -f "$SCORECARD" ]; then
  text="$(printf '*Nightly Scorecard*\n%s\n' "$SCORECARD")"
  curl -sS -X POST -H 'Content-type: application/json' --data "$(jq -n --arg t "$text" '{text:$t}')" "$SLACK_WEBHOOK" >/dev/null || true
  echo "[OK] posted to Slack"
fi

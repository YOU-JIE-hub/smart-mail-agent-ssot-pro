#!/usr/bin/env bash
# 產生 demo eml → 執行 E2E → 若 cases 空則 bootstrap → 後處理 → 顯示最新摘要
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"

bash "$ROOT/scripts/sma_make_demo_eml.sh"

bash "$ROOT/sma_oneclick_all.sh" || true

latest="$(ls -1dt "$ROOT"/reports_auto/e2e_mail/* 2>/dev/null | head -n1 || true)"
if [ -n "$latest" ] && [ -f "$latest/cases.jsonl" ] && [ ! -s "$latest/cases.jsonl" ]; then
  bash "$ROOT/scripts/sma_bootstrap_from_demo.sh"
  newrun="$(ls -1dt "$ROOT"/reports_auto/e2e_mail/* 2>/dev/null | head -n1 || true)"
  [ -n "$newrun" ] && bash "$ROOT/scripts/sma_oneclick_after_run.sh" --run-dir "$newrun" || true
else
  bash "$ROOT/scripts/sma_oneclick_after_run.sh" --run-dir "$latest" || true
fi

echo
echo "# LATEST"
sed -n '1,160p' "$ROOT/reports_auto/status/LATEST.md" || true

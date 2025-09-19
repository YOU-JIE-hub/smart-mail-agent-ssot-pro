#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
bash scripts/api_up_env.sh
bash scripts/sanity_all.sh
bash scripts/tri_eval_fixlabels.sh
bash scripts/tri_eval_report.sh
bash scripts/eval_kie.sh
bash scripts/eval_spam.sh
bash scripts/gate_accept.sh
TS="$(date +%Y%m%dT%H%M%S)"; SUM="reports_auto/status/CI_SUMMARY_${TS}.md"
{
  echo "# CI SUMMARY ($TS)"
  echo
  echo "## Intent"
  LAST_I="$(ls -1dt reports_auto/eval_fix/2* | head -n1)"; echo "- JSON: $LAST_I/tri_results_fixed.json"
  echo "- MD  : reports_auto/status/INTENTS_SUMMARY_$(basename "$LAST_I").md"
  echo
  echo "## KIE"
  LAST_K="$(ls -1dt reports_auto/kie_eval/2* 2>/dev/null | head -n1 || true)"; [ -n "$LAST_K" ] && echo "- JSON: $LAST_K/report.json" || echo "- JSON: <skipped>"
  echo
  echo "## Spam"
  LAST_S="$(ls -1dt reports_auto/spam_eval/2* 2>/dev/null | head -n1 || true)"; [ -n "$LAST_S" ] && echo "- JSON: $LAST_S/report.json" || echo "- JSON: <skipped>"
  echo
  echo "## Logs"
  echo "- SERVER: $ROOT/reports_auto/ERR/server.log"
  echo "- PY_LAST: $ROOT/reports_auto/ERR/py_last_trace.txt"
} > "$SUM"
echo "$SUM"

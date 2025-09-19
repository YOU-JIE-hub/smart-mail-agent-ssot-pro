#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
TS="$(date +%Y%m%dT%H%M%S)"
OUT="release_${TS}.tar.gz"
LATEST_SCORE="$(ls -t reports_auto/status/SCORECARD_* 2>/dev/null | head -n1 || true)"
tar -czf "$OUT" \
  artifacts_prod/intent_rules_calib_v11c.json \
  artifacts_prod/ens_thresholds.json \
  artifacts_prod/intent_stacker_v1.pkl 2>/dev/null || true
[ -n "$LATEST_SCORE" ] && tar -rzf "$OUT" "$LATEST_SCORE" || true
# 附上最近一次 metrics
for f in $(ls -t reports_auto/eval/*/metrics_* 2>/dev/null | head -n3); do tar -rzf "$OUT" "$f"; done
for f in $(ls -t reports_auto/kie_eval/*/metrics_* 2>/dev/null | head -n3); do tar -rzf "$OUT" "$f"; done
echo "[OK] release bundle => $OUT"

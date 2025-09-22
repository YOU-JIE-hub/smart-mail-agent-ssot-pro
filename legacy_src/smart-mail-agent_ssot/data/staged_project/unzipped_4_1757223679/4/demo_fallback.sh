#!/usr/bin/env bash
set -Eeuo pipefail
T="${1:-0.52}"
M="${2:-0.10}"
python -X faulthandler .sma_tools/pro_fallback_threshold.py \
  --model artifacts/intent_pro_cal.pkl \
  --test  data/intent/external_realistic_test.clean.jsonl \
  --threshold "$T" --margin "$M" \
  --out_prefix reports_auto/external_fallback \
  --scan --only-tech --rules-guard
echo; echo "=== Fallback 評分（含對照） ==="
sed -n '1,120p' reports_auto/external_fallback_eval.txt || true
echo; echo "=== Fallback 混淆矩陣（前幾行） ==="
sed -n '1,10p' reports_auto/external_fallback_confusion.tsv || true
echo; echo "=== Fallback 錯誤前 10 ==="
sed -n '1,11p' reports_auto/external_fallback_errors.tsv || true

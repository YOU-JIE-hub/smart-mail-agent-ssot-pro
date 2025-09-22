#!/usr/bin/env bash
set -Eeuo pipefail
T="${1:-0.58}"
M="${2:-0.10}"

python -X faulthandler .sma_tools/pro_fallback_threshold.py \
  --model artifacts/intent_pro_cal.pkl \
  --test  data/intent/external_realistic_test.clean.jsonl \
  --threshold "$T" --margin "$M" \
  --out_prefix reports_auto/external_fallback \
  --scan

echo; echo "=== Fallback 評分（含對照） ==="
sed -n '1,80p' reports_auto/external_fallback_eval.txt || true

echo; echo "=== Fallback 混淆矩陣（前幾行） ==="
sed -n '1,10p' reports_auto/external_fallback_confusion.tsv || true

echo; echo "=== Fallback 錯誤前 10 ==="
sed -n '1,11p' reports_auto/external_fallback_errors.tsv || true

echo; echo "=== 關鍵錯誤：gold=other, pred=tech_support ==="
awk -F'\t' 'NR==1||($3=="other" && $4=="tech_support")' \
  reports_auto/external_fallback_errors.tsv | sed -n '1,11p' || true

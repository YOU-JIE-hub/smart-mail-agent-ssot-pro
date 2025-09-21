#!/usr/bin/env bash
source .sma_tools/env_guard.sh
set -euo pipefail
vals=(0.10 0.12 0.14 0.16 0.18 0.20 0.22 0.24 0.26 0.28 0.30 0.32 0.34 0.36 0.38 0.40)
echo "thr | macroF1 | ham(P/R/F1) | spam(P/R/F1)"
for thr in "${vals[@]}"; do
  printf '{"threshold": %.2f}\n' "$thr" > artifacts/spam_thresholds.json
  out=$(PYTHONPATH=src python scripts/run_spam_eval.py \
    --data data/spam/val.jsonl \
    --rules .sma_tools/spam_rules.yml \
    --model artifacts/spam_rules_lr.pkl \
    --thresholds artifacts/spam_thresholds.json 2>/dev/null | sed -n '1,6p')
  line=$(echo "$out" | tr '\n' ' | ')
  echo "$thr | $line"
done

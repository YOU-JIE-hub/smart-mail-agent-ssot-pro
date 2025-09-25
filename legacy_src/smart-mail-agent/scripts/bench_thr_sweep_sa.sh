#!/usr/bin/env bash
source .sma_tools/env_guard.sh
set -euo pipefail
printf "thr\tmacroF1\thamP\thamR\thamF1\tspamP\tspamR\tspamF1\n"
for t in $(seq 0.10 0.01 0.60); do
  printf '{"threshold": %.2f}\n' "$t" > artifacts/spam_thresholds.json
  out=$(PYTHONPATH=src python scripts/run_spam_eval.py \
    --data data/benchmarks/spamassassin.jsonl \
    --rules .sma_tools/spam_rules.yml \
    --model artifacts/spam_rules_lr.pkl \
    --thresholds artifacts/spam_thresholds.json 2>/dev/null | sed -n '1,6p')
  macro=$(echo "$out" | sed -n '1p' | sed -E 's/.*macro_f1=([0-9.]+).*/\1/')
  ham=$(echo "$out"   | sed -n '2p' | sed -E 's/.*= ([0-9.]+)\/([0-9.]+)\/([0-9.]+).*/\1\t\2\t\3/')
  spam=$(echo "$out"  | sed -n '3p' | sed -E 's/.*= ([0-9.]+)\/([0-9.]+)\/([0-9.]+).*/\1\t\2\t\3/')
  echo -e "$t\t$macro\t$ham\t$spam"
done

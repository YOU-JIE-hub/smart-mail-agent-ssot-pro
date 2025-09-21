#!/usr/bin/env bash
set -Eeuo pipefail
# Script for running Pro version of training and evaluation
SEED=42
python .sma_tools/oneclick_train_eval_pro.sh downloads/external_realistic_test.jsonl

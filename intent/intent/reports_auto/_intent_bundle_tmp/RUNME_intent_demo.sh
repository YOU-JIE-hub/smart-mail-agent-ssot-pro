#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

# 嘗試自動找到模型與門檻
MODEL="$(ls "$here"/../artifacts/intent_*_cal.pkl 2>/dev/null | head -n1 || true)"
[[ -z "${MODEL:-}" ]] && MODEL="$(ls "$here"/../artifacts/releases/intent/current/intent_*_cal.pkl 2>/dev/null | head -n1 || true)"
[[ -z "${MODEL:-}" ]] && { echo "[FATAL] 找不到 intent_*_cal.pkl"; exit 10; }

THR="$(ls "$here"/../reports_auto/intent_thresholds.json 2>/dev/null || true)"
[[ -z "${THR:-}" ]] && THR="$(ls "$here"/../artifacts/releases/intent/current/intent_thresholds.json 2>/dev/null || true)"
[[ -z "${THR:-}" ]] && { echo "[FATAL] 找不到 intent_thresholds.json"; exit 11; }

TEST="${1:-$here/../data/intent/external_realistic_test.clean.jsonl}"
echo "[USE] MODEL=$MODEL"
echo "[USE] THR=$THR"
echo "[USE] TEST=$TEST"

python "$here/../.sma_tools/runtime_threshold_router.py" \
  --model "$MODEL" \
  --input "$TEST" \
  --out_preds "$here/preds.jsonl" \
  --eval

echo "[OK] 完成，輸出：$here/preds.jsonl"

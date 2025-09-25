#!/usr/bin/env bash
set -Eeuo pipefail
cd "$HOME/projects/smart-mail-agent" || { echo "[FAIL] no project"; exit 1; }
([ -f .venv/bin/activate ] && . .venv/bin/activate) || ([ -f "$HOME/.venv/sma/bin/activate" ] && . "$HOME/.venv/sma/bin/activate") || true
python - <<'PY'
import importlib,sys
miss=[m for m in ['numpy','scipy','sklearn'] if importlib.util.find_spec(m) is None]
sys.exit(1 if miss else 0)
PY
python .sma_tools/auto_augment_train.py 2>&1 | tee .sma_tools/logs/auto_last_run.log
echo "[PRED-1]"
python .sma_tools/predict_full.py --model artifacts/intent_svm_plus_auto.pkl --text 'Subject: 退費流程與條款請提供'
echo "[PRED-2]"
python .sma_tools/predict_full.py --model artifacts/intent_svm_plus_auto.pkl --text 'Hi 支援，API /v1/orders 在 prod 回 500，請查 log 並提供修復 ETA'
echo "[PRED-3]"
python .sma_tools/predict_full.py --model artifacts/intent_svm_plus_auto.pkl --text '請把發票寄送信箱改為 <EMAIL> 並保留 <EMAIL> 在副本'
echo "[DONE] artifacts/intent_svm_plus_auto.pkl 以及 reports_auto/* 已更新"

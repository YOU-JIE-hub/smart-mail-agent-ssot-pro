#!/usr/bin/env bash
set -Eeuo pipefail
cd "$HOME/projects/smart-mail-agent"
([ -f .venv/bin/activate ] && . .venv/bin/activate) || ([ -f "$HOME/.venv/sma/bin/activate" ] && . "$HOME/.venv/sma/bin/activate") || true
python .sma_tools/train_from_split.py
echo "[PRED-1]"; python .sma_tools/predict_full.py --model artifacts/intent_svm_plus_split.pkl --text 'Subject: 退費流程與條款請提供'
echo "[PRED-2]"; python .sma_tools/predict_full.py --model artifacts/intent_svm_plus_split.pkl --text 'Hi 支援，API /v1/orders 在 prod 回 500，請查 log 並提供修復 ETA'
echo "[PRED-3]"; python .sma_tools/predict_full.py --model artifacts/intent_svm_plus_split.pkl --text '請把發票寄送信箱改為 <EMAIL> 並保留 <EMAIL> 在副本'

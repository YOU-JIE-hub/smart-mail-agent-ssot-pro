#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
log(){ printf '[%s] %s\n' "$(date +%F' '%T)" "$*"; }

# venv 基礎依賴（已裝就跳過）
if [[ ! -d .venv_clean ]]; then python3 -m venv .venv_clean; fi
source .venv_clean/bin/activate
python -m pip -q install --upgrade pip wheel setuptools >/dev/null
python -m pip -q install numpy scipy scikit-learn joblib pandas >/dev/null

mkdir -p reports_auto

# 1) SPAM
log "Eval SPAM -> reports_auto/spam_cn_eval.txt"
PYTHONPATH=src python scripts/sma_quick_eval.py --data data/cn_spam_eval.jsonl --out reports_auto/spam_cn_eval.txt || true

# 2) INTENT（重建 6 維規則 → 29233）
log "Eval INTENT (reconstruct) -> reports_auto/intent_eval_exact.txt"
python .sma_tools/intent_eval_reconstruct.py --model artifacts/intent_pro_cal.pkl \
       --data data/intent/external_realistic_test.clean.jsonl \
       --out  reports_auto/intent_eval_exact.txt

# 3) KIE
log "Eval KIE -> reports_auto/kie_eval.txt"
python .sma_tools/kie_eval_strict.py --model_dir artifacts/releases/kie_xlmr/current \
       --test data/kie/test.jsonl --out_prefix reports_auto/kie_eval || true

log "[reports] 在 ./reports_auto/"

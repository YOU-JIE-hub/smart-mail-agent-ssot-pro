#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
log(){ printf '[%s] %s\n' "$(date +%F' '%T)" "$*"; }

# venv
[[ -d .venv_clean ]] || python3 -m venv .venv_clean
# shellcheck disable=SC1091
source .venv_clean/bin/activate
python -m pip -q install --upgrade pip wheel setuptools >/dev/null
python -m pip -q install numpy scipy scikit-learn joblib pandas >/dev/null

mkdir -p reports_auto data data/kie

# Chinese spam set（有就跳過）
if [[ ! -f data/cn_spam_eval.jsonl ]]; then
  if [[ -x scripts/sma_make_cn_eval_sets_v2.sh ]]; then bash scripts/sma_make_cn_eval_sets_v2.sh
  elif [[ -x scripts/sma_make_cn_eval_sets.sh   ]]; then bash scripts/sma_make_cn_eval_sets.sh
  fi
fi

# 1) SPAM
log "Eval SPAM -> reports_auto/spam_cn_eval.txt"
PYTHONPATH=src python scripts/sma_quick_eval.py --data data/cn_spam_eval.jsonl --out reports_auto/spam_cn_eval.txt || true

# 2) INTENT（用 router；我們已補 __main__/Pipeline/dict 支援）
log "Eval INTENT (router) -> reports_auto/intent_eval_router.txt"
python .sma_tools/runtime_threshold_router.py \
  --model artifacts/intent_pro_cal.pkl \
  --input data/intent/external_realistic_test.clean.jsonl \
  --thresholds reports_auto/intent_thresholds.json \
  --out_preds reports_auto/intent_preds.jsonl \
  --eval > reports_auto/intent_eval_router.txt || true
[[ -s reports_auto/intent_eval_router.txt ]] && echo "[OK] wrote reports_auto/intent_eval_router.txt"

# 3) KIE（若有權重就安裝依賴並跑）
if [[ -d artifacts/releases/kie_xlmr/current && -f .sma_tools/kie_eval_strict.py ]]; then
  python -m pip -q install --index-url https://download.pytorch.org/whl/cpu torch==2.2.2 >/dev/null
  python -m pip -q install "transformers>=4.39,<4.42" >/dev/null
  log "Eval KIE -> reports_auto/kie_eval.txt"
  python .sma_tools/kie_eval_strict.py \
    --model_dir artifacts/releases/kie_xlmr/current \
    --test data/kie/test.jsonl \
    --out_prefix reports_auto/kie_eval || true
fi

log "[reports] 在 ./reports_auto/"

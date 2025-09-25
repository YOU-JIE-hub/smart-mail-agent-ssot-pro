#!/usr/bin/env bash
set -Eeuo pipefail
PROJ="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$PROJ"
([ -f .venv/bin/activate ] && . .venv/bin/activate) || ([ -f "$HOME/.venv/sma/bin/activate" ] && . "$HOME/.venv/sma/bin/activate") || true
mkdir -p .sma_tools/logs
python - <<'PY'
import importlib,sys
miss=[m for m in ['numpy','scipy','sklearn'] if importlib.util.find_spec(m) is None]
assert not miss, f"missing:{miss}"
PY
python .sma_tools/grid_search_train.py 2>&1 | tee .sma_tools/logs/opt_grid.log
python .sma_tools/tune_thresholds.py 2>&1 | tee -a .sma_tools/logs/opt_grid.log
echo "[OK] best model -> artifacts/intent_svm_plus_best.pkl ; grid -> reports_auto/opt_grid.tsv"

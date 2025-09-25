#!/usr/bin/env bash
source .sma_tools/env_guard.sh
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$PROJECT_ROOT"
source .venv/bin/activate
export PYTHONPATH=.:src
echo "[deps] ensure sklearn/joblib"
python - <<'PY' || { pip install -U scikit-learn joblib >/dev/null; }
import importlib; importlib.import_module("sklearn"); importlib.import_module("joblib")
print("deps-ok")
PY
echo "[train] intent+spam (ML)"
python -m models.intent.train_ml
python -m models.spam.train_ml
echo "[ok] artifacts_ml prepared under models/*/artifacts_ml"
echo "Tip: export SMA_INTENT_BACKEND=ml; export SMA_SPAM_BACKEND=ml; then run: make test-models"

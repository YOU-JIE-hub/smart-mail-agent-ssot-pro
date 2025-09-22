#!/usr/bin/env bash
set -Eeuo pipefail
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
python -m pip install -U pip
pip install -r requirements-dev.txt
# 輕量依賴（用於部分指標/metrics）
pip install scikit-learn numpy scipy
pytest

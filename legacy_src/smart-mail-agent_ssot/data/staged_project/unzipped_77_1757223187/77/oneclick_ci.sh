#!/usr/bin/env bash
set -Eeuo pipefail
PROJ="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$PROJ"
([ -f .venv/bin/activate ] && . .venv/bin/activate) || ([ -f "$HOME/.venv/sma/bin/activate" ] && . "$HOME/.venv/sma/bin/activate") || true
python - <<'PY'
import importlib,sys
miss=[m for m in ['numpy','scipy','sklearn'] if importlib.util.find_spec(m) is None]
assert not miss, f"missing:{miss}"
PY
python - <<'PY'
import py_compile, glob
[py_compile.compile(f, doraise=True) for f in glob.glob(".sma_tools/*.py")]
print("[OK] compile")
PY
python .sma_tools/auto_augment_train.py
python .sma_tools/calibrate_and_card.py
python .sma_tools/route_predict.py --text 'Hi 支援，API /v1/orders 在 prod 回 500，請查 log 並提供修復 ETA'
echo "[OK] ci"

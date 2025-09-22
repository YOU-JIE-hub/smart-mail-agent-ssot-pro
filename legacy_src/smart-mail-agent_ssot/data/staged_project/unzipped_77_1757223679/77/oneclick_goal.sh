#!/usr/bin/env bash
set -Eeuo pipefail
PROJ="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
IN="${1:-}"; OUT="${2:-}"
cd "$PROJ"
([ -f .venv/bin/activate ] && . .venv/bin/activate) || ([ -f "$HOME/.venv/sma/bin/activate" ] && . "$HOME/.venv/sma/bin/activate") || true
python - <<'PY'
import importlib,sys
miss=[m for m in ['numpy','scipy','sklearn'] if importlib.util.find_spec(m) is None]
assert not miss, f"missing:{miss}"
PY
mkdir -p .sma_tools/logs artifacts dist reports_auto
python .sma_tools/auto_augment_train.py
python .sma_tools/calibrate_and_card.py
MODEL="artifacts/intent_svm_plus_auto_cal.pkl"; [ -f "$MODEL" ] || MODEL="artifacts/intent_svm_plus_auto.pkl"
ts=$(date +%Y%m%d_%H%M%S); pkg="dist/sma_intent_router_${ts}.zip"; tmp="dist/_pkg_${ts}"
mkdir -p "$tmp"
cp "$MODEL" "$tmp"/
cp .sma_tools/predict_full.py .sma_tools/extract_fields.py .sma_tools/priority_rules.py .sma_tools/route_predict.py "$tmp"/
[ -f .sma_tools/router_config.json ] && cp .sma_tools/router_config.json "$tmp"/
( cd "$tmp" && zip -qr "../$(basename "$pkg")" . )
rm -rf "$tmp"
if [ -n "$IN" ] && [ -n "$OUT" ]; then
  python .sma_tools/route_predict.py --input "$IN" --output "$OUT"
fi
echo "$MODEL"
echo "$pkg"

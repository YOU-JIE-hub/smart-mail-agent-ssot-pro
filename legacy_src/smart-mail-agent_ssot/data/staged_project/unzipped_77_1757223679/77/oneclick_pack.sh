#!/usr/bin/env bash
set -Eeuo pipefail
PROJ="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$PROJ"
([ -f .venv/bin/activate ] && . .venv/bin/activate) || ([ -f "$HOME/.venv/sma/bin/activate" ] && . "$HOME/.venv/sma/bin/activate") || true
mkdir -p dist
MODEL="artifacts/intent_svm_plus_auto_cal.pkl"; [ -f "$MODEL" ] || MODEL="artifacts/intent_svm_plus_auto.pkl"
ts=$(date +%Y%m%d_%H%M%S)
pkg="dist/sma_intent_router_${ts}.zip"
tmp="dist/_pkg_${ts}"
mkdir -p "$tmp"
cp "$MODEL" "$tmp"/ 2>/dev/null || true
cp .sma_tools/predict_full.py .sma_tools/extract_fields.py .sma_tools/priority_rules.py .sma_tools/route_predict.py "$tmp"/
[ -f .sma_tools/router_config.json ] && cp .sma_tools/router_config.json "$tmp"/
cd "$tmp" && zip -qr "../$(basename "$pkg")" . && cd - >/dev/null
sha256sum "$pkg" | tee "${pkg}.sha256"
rm -rf "$tmp"
echo "[PKG] $pkg"

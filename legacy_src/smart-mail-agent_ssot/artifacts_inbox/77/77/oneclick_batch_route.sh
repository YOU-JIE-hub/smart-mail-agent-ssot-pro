#!/usr/bin/env bash
set -Eeuo pipefail
PROJ="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
IN="${1:-}"; OUT="${2:-}"
[ -n "$IN" ] && [ -n "$OUT" ] || { echo "usage: $0 IN.jsonl OUT.jsonl"; exit 2; }
cd "$PROJ"
([ -f .venv/bin/activate ] && . .venv/bin/activate) || ([ -f "$HOME/.venv/sma/bin/activate" ] && . "$HOME/.venv/sma/bin/activate") || true
python .sma_tools/route_predict.py --input "$IN" --output "$OUT"
echo "[OK] -> $OUT"

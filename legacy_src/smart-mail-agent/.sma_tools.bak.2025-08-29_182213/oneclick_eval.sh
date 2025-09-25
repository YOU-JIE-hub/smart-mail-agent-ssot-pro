#!/usr/bin/env bash
set -Eeuo pipefail
PROJ="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
IN="${1:-}"; OUTERR="${2:-}"
[ -n "$IN" ] || { echo "usage: $0 /abs/path/test.jsonl [/abs/path/miscls.jsonl]"; exit 2; }
cd "$PROJ"
([ -f .venv/bin/activate ] && . .venv/bin/activate) || ([ -f "$HOME/.venv/sma/bin/activate" ] && . "$HOME/.venv/sma/bin/activate") || true
mkdir -p .sma_tools/logs
ts=$(date +%Y%m%d_%H%M%S)
LOG=".sma_tools/logs/eval_${ts}.log"
python .sma_tools/eval_only.py --input "$IN" ${OUTERR:+--errors_out "$OUTERR"} 2>&1 | tee "$LOG"
echo "[LOG] $LOG"

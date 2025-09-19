#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT" || { echo "[FATAL] $ROOT"; exit 2; }
[[ -d .venv ]] || python3 -m venv .venv
. .venv/bin/activate 2>/dev/null || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:.sma_tools:${PYTHONPATH:-}"
if [[ -f scripts/oneclick_v3.sh ]]; then
  exec bash scripts/oneclick_v3.sh
else
  echo "[WARN] 沒有 scripts/oneclick_v3.sh；略過"
fi

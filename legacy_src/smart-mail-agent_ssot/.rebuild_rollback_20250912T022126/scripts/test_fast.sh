#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT"
. .venv/bin/activate || true
: "${OFFLINE:=0}"
if [[ "$OFFLINE" = "0" ]]; then python -m pip -q install pytest==8.2.1 || true; fi
python -m pytest -q -rA || true

#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: env_guard.sh requires bash"; exit 2; }
set -Eeuo pipefail
export PYTHONNOUSERSITE=1
if [ -d ".venv" ] && [ -f ".venv/bin/activate" ]; then . ".venv/bin/activate"; fi
export PYTHONPATH="$(pwd)/src:${PYTHONPATH:-}"
echo "SMA PRINT OK :: ENV GUARDED (PYTHONPATH=$PYTHONPATH)"

#!/usr/bin/env bash
set -Eeuo pipefail
cd "${SMA_ROOT:-$PWD}"
if [[ -x .venv_clean/bin/activate ]]; then . .venv_clean/bin/activate
elif [[ -x .venv/bin/activate ]]; then . .venv/bin/activate
fi
export PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
python -m smart_mail_agent.cli.replay_actions "$@"

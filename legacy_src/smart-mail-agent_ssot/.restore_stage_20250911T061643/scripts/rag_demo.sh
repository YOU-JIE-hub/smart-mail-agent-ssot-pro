#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$PWD}"; cd "$ROOT"
. .venv_clean/bin/activate
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
python -m smart_mail_agent.cli.rag_build
python -m smart_mail_agent.cli.rag_query "${1:-請總結重點與條款限制?}"

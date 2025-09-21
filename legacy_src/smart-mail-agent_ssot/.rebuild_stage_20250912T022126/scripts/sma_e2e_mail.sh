#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
EMLDIR="${1:-data/demo_eml}"
PY="${PY:-python}"
export PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"
exec "$PY" -u -m smart_mail_agent.cli.e2e --eml-dir "$EMLDIR"

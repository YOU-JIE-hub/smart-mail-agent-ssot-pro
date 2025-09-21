#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$PWD}"; cd "$ROOT"
python -m smart_mail_agent.cli.kb_ingest "${1:-kb_docs}"

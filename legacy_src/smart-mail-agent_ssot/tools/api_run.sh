#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}" python tools/api_server.py

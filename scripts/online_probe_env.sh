#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$ROOT/.venv/bin/activate" ] && . "$ROOT/.venv/bin/activate" || true
export PYTHONNOUSERSITE=1 PYTHONPATH="$ROOT:$ROOT/src:${PYTHONPATH:-}"
exec "$ROOT/scripts/online_probe.sh" "$@"

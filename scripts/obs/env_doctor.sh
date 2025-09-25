#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
[ -f ".venv/bin/activate" ] && . ".venv/bin/activate" || true
export PYTHONNOUSERSITE=1 PYTHONPATH="$ROOT:$ROOT/src:${PYTHONPATH:-}"
python tools/config_facade/env_doctor.py >/dev/null || true
LAST="$(ls -t reports_auto/status/ENV_DOCTOR_*.md 2>/dev/null | head -n1 || true)"
echo "OUT MD: ${LAST:-N/A}"

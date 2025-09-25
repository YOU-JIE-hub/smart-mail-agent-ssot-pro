#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
[ -x .venv/bin/python ] && . .venv/bin/activate || true
export PYTHONPATH=.
: "${COV_UNDER:=95}"
pytest --cov-fail-under="$COV_UNDER"
coverage-badge -o assets/badges/coverage.svg -f
echo "Done. Badge at assets/badges/coverage.svg"

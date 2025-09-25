#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m venv "$PROJECT_ROOT/.venv" 2>/dev/null || true
# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate"
python -m pip -q install --upgrade pip
python -m pip -q install pytest coverage pyyaml requests beautifulsoup4
echo "[bootstrap] ok"

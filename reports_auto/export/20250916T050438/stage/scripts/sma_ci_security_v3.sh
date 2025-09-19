#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${1:-}" == "--debug" ]] && set -x
# shellcheck disable=SC1091
source .venv_clean/bin/activate
export PYTHONPATH="$(git rev-parse --show-toplevel)/src:${PYTHONPATH:-}"
echo "[CI] Ruff fmt check"; ruff format --check src tests
echo "[CI] Ruff lint"; ruff check src tests
echo "[CI] Bandit"; bandit -q -r src -ll
echo "[CI] pip-audit"; pip-audit -q
echo "[CI] pytest"; pytest -q
echo "[CI] OK"

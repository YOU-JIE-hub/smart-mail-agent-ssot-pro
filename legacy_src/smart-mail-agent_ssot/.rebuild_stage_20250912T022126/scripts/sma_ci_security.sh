#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv_clean/bin/activate

echo "[CI] Ruff (lint + format check)"
ruff check src tests
ruff format --check src tests

echo "[CI] Bandit"
python -m pip -q install bandit || true
bandit -q -r src -x "alembic,tests"

echo "[CI] pip-audit"
python -m pip -q install pip-audit || true
pip-audit || true

echo "[CI] Pytest"
pytest -q
echo "[CI] OK"

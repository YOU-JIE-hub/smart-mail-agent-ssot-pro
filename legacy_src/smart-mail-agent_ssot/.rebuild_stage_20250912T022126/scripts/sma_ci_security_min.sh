#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC1091
source .venv_clean/bin/activate
ruff format --check src tests
ruff check src tests
pytest -q

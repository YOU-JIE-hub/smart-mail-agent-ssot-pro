#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT"
. .venv/bin/activate || true
python -m ruff check src tests --fix || true
python -m black -q src tests || true
python -m isort -q src tests || true
echo "[OK] 格式檢查完成"

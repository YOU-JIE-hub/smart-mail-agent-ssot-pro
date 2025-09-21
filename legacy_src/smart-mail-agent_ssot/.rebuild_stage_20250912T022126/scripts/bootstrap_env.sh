#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$PWD}"
cd "$ROOT"
VENV=".venv_clean"
PY="${PYTHON_BIN:-python3}"

if [[ ! -d "$VENV" ]]; then
  echo "[BOOT] create venv at $VENV"
  "$PY" -m venv "$VENV"
fi

# 只允許在 venv 內 pip；避免汙染系統或使用者站台套件
set +u
source "$VENV/bin/activate"
set -u
export PIP_REQUIRE_VIRTUALENV=1
export PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
python -V

if [[ -f requirements.txt ]]; then
  echo "[BOOT] install requirements in venv (no global pollution)"
  python -m pip install --upgrade pip
  python -m pip install --no-cache-dir -r requirements.txt
else
  echo "[BOOT] no requirements.txt, skip"
fi
echo "[BOOT] ok"

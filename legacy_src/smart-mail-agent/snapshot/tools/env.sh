#!/usr/bin/env bash
# 請用： source tools/env.sh
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "[env] 請使用：source tools/env.sh"; exit 1
fi
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  echo "[env] 找不到 .venv，先執行：bash tools/bootstrap.sh"; return 1
fi
# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate" || { echo "[env] venv 啟用失敗"; return 1; }
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/src"
: "${OFFLINE:=1}"; export OFFLINE
python - <<'PY' || true
import os, sys
print(f"[env] venv: {sys.prefix}")
print(f"[env] PYTHONPATH: {os.environ.get('PYTHONPATH')}")
print(f"[env] OFFLINE={os.environ.get('OFFLINE')}")
PY

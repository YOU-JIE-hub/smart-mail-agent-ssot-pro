#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
[ -d "$ROOT/.git" ] && [ -d "$ROOT/src" ] || { echo "[FAIL] 非有效專案根：$ROOT"; exit 2; }
cd "$ROOT"

if [ -x .venv/bin/python ]; then PY=.venv/bin/python
elif [ -x "$HOME/.venv/sma/bin/python" ]; then PY="$HOME/.venv/sma/bin/python"
else PY="$(command -v python3 || command -v python || true)"
fi
[ -n "$PY" ] || { echo "[FAIL] 找不到 python"; exit 3; }

export OFFLINE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$PWD/src:$PWD"

echo "[INFO] 執行 pytest + coverage（不安裝、不創建環境）"
"$PY" -m pytest -q       --maxfail=1 --disable-warnings       --cov=src --cov=modules --cov=smart_mail_agent       --cov-report=term-missing       --cov-report=xml:coverage.xml

"$PY" - <<'PY' || exit 0
try:
    import runpy
    runpy.run_module("genbadge", run_name="__main__")
except Exception:
    raise SystemExit(0)
PY
if [ -f coverage.xml ]; then
  mkdir -p badges
  "$PY" -m genbadge coverage -i coverage.xml -o badges/coverage.svg || true
  echo "[INFO] 已嘗試輸出 badges/coverage.svg（若缺 genbadge 將略過）"
fi
echo "[DONE] 覆蓋率流程完成"

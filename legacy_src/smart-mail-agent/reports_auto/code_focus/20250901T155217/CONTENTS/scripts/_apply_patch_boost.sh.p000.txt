#!/usr/bin/env bash
source .sma_tools/env_guard.sh
# _apply_patch_boost.sh — 新增安全測試與覆蓋率腳本（不安裝、不創建 venv）
set -Eeuo pipefail
trap 'ec=$?; echo "[ERROR] 失敗於第 $LINENO 行（exit=$ec）" >&2' ERR

ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
[ -d "$ROOT/.git" ] && [ -d "$ROOT/src" ] || { echo "[FAIL] 非有效專案根：$ROOT"; exit 96; }
cd "$ROOT"

# 只用既有 Python
if [ -x .venv/bin/python ]; then PY=.venv/bin/python
elif [ -x "$HOME/.venv/sma/bin/python" ]; then PY="$HOME/.venv/sma/bin/python"
else PY="$(command -v python3 || command -v python || true)"
fi
[ -n "$PY" ] || { echo "[FAIL] 找不到 python"; exit 98; }

export OFFLINE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$PWD/src:$PWD"
echo "[INFO] ROOT=$ROOT"
echo "[INFO] PY=$("$PY" -V 2>&1)"
echo "[INFO] OFFLINE=$OFFLINE"
echo "[INFO] PYTHONPATH=$PYTHONPATH"

mkdir -p tests/boost scripts

# 測試 1：兩個 CLI 入口的 --help（只印用法，無副作用）
cat > tests/boost/test_cli_help.py <<'PY'
import os, sys, subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
PYEXE = sys.executable
def _run_help(relpath: str):
    p = ROOT / relpath
    if not p.exists():
        return None
    env = os.environ.copy()
    env.setdefault("OFFLINE", "1")
    env["PYTHONPATH"] = f"{ROOT/'src'}:{ROOT}"
    cp = subprocess.run([PYEXE, str(p), "--help"], cwd=str(ROOT), env=env,
                        capture_output=True, text=True)
    out = (cp.stdout or "") + (cp.stderr or "")
    assert cp.returncode == 0, f"help failed: {relpath}\nstdout={cp.stdout}\nstderr={cp.stderr}"
    assert "usage" in out.lower(), f"no usage in help: {relpath}\n{out}"
    return out
def test_help_routing_entry():
    _run_help("src/smart_mail_agent/routing/run_action_handler.py")
def test_help_legacy_entry():
    _run_help("src/run_action_handler.py")
PY

# 測試 2：importlib 健檢（避免再誤判）
cat > tests/boost/test_importlib_sanity.py <<'PY'
def test_importlib_has_util():
    import importlib
    assert hasattr(importlib, "util")
PY

# 覆蓋率腳本（僅用現有環境執行 pytest；無副作用）
cat > scripts/boost_coverage_now.sh <<'BASH'
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
echo "[INFO] pytest + coverage"
"$PY" -m pytest -q --maxfail=1 --disable-warnings \
  --cov=src --cov=modules --cov=smart_mail_agent \
  --cov-report=term-missing --cov-report=xml:coverage.xml
# 若有 genbadge 才產生徽章
"$PY" - <<'PY' || exit 0
import runpy
try:
    runpy.run_module("genbadge", run_name="__main__")
except Exception:
    raise SystemExit(0)
PY
if [ -f coverage.xml ]; then
  mkdir -p badges
  "$PY" -m genbadge coverage -i coverage.xml -o badges/coverage.svg || true
  echo "[INFO] 嘗試更新 badges/coverage.svg（若缺 genbadge 將略過）"
fi
echo "[DONE] 覆蓋率流程完成"
BASH
chmod +x scripts/boost_coverage_now.sh

# 僅驗證新增測試是否可跑（不跑整倉）
if "$PY" - <<'PY' >/dev/null 2>&1; then
try:
    import pytest  # noqa
    print("[CHECK] pytest 已安裝")
except Exception:
    raise SystemExit(1)
PY
then
  echo "[INFO] 驗證新增測試（tests/boost）"
  "$PY" -m pytest -q tests/boost -k "cli_help or importlib_sanity"
  echo "[NEXT] 如需完整覆蓋率，請執行：scripts/boost_coverage_now.sh"
else
  echo "[NEXT] 當前環境未安裝 pytest；已完成檔案新增，可待環境就緒後執行 scripts/boost_coverage_now.sh"
fi

echo "[DONE] 補丁完成"
exit 0

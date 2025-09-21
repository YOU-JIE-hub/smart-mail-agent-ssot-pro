#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "❌ 失敗於第 $LINENO 行（exit=$?）" >&2' ERR

# 0) 進虛擬環境 & 安裝工具
if [ ! -x ".venv/bin/python" ]; then python3 -m venv .venv; fi
. .venv/bin/activate
python -m pip -q install -U pip wheel >/dev/null
python -m pip -q install -U ruff pytest >/dev/null

# 1) Lint 設定（排除舊目錄與備份資料夾）
cat > ruff.toml <<'TOML'
line-length = 100
target-version = "py310"
select = ["E", "F", "I"]     # 基本錯誤 + import 排序
ignore = []                  # 目前不放寬規則
extend-exclude = [
  ".venv", "build", "dist",
  ".z_legacy_*", ".backup_conflicts_*", ".release_stage",
  "legacy_tests", "tests/internal_smoke", "tests/ai_rpa"
]
TOML

# 2) Pytest 設定
cat > pytest.ini <<'INI'
[pytest]
addopts = -q
testpaths = tests
INI

# 3) 最小測試：檢查 CLI 版本輸出
mkdir -p tests
cat > tests/test_cli_version.py <<'PY'
from __future__ import annotations
import smart_mail_agent as pkg
from smart_mail_agent.cli.sma import main

def test_cli_prints_version(capsys):
    rc = main(["--version"])
    out = capsys.readouterr().out.strip()
    assert pkg.__version__ in out
    assert rc == 0
PY

# 4) 重新安裝（editable）以確保當前 src 生效
python -m pip -q install -e . >/dev/null

# 5) 執行 Lint（自動修部分）與測試
echo "— Ruff（src/）—"
ruff check src --fix

echo "— Pytest —"
pytest

# 6) 額外 sanity check（應輸出 0.4.0）
echo "— CLI sanity —"
python -S -m smart_mail_agent.cli.sma --version

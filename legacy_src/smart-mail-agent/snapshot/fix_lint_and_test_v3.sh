#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "❌ 失敗於第 $LINENO 行（exit=$?）" >&2' ERR

# 0) venv & tools
if [ ! -x ".venv/bin/python" ]; then python3 -m venv .venv; fi
. .venv/bin/activate
python -m pip -q install -U pip wheel >/dev/null
python -m pip -q install -U ruff pytest >/dev/null

# 1) 用新版語法重寫 ruff.toml，並暫時忽略 E501
cat > ruff.toml <<'TOML'
line-length = 100
target-version = "py310"

[lint]
select = ["E", "F", "I"]
ignore = [
  "E701",  # 同行多語句（:）
  "E702",  # 同行多語句（;）
  "E402",  # imports 不在頂部
  "E741",  # 模糊變數名，如 l
  "F403",  # wildcard import
  "F811",  # 重複定義
  "E501",  # 行過長（暫時忽略，之後再收斂）
]

# 排除舊檔與備份資料夾
extend-exclude = [
  ".venv", "build", "dist",
  ".z_legacy_*", ".backup_conflicts_*", ".release_stage",
  "legacy_tests", "tests/internal_smoke", "tests/ai_rpa"
]
TOML

# 2) pytest 設定（保險補上）
[ -f pytest.ini ] || cat > pytest.ini <<'INI'
[pytest]
addopts = -q
testpaths = tests
INI

# 3) 確保有最小測試
mkdir -p tests
[ -f tests/test_cli_version.py ] || cat > tests/test_cli_version.py <<'PY'
from __future__ import annotations
import smart_mail_agent as pkg
from smart_mail_agent.cli.sma import main

def test_cli_prints_version(capsys):
    rc = main(["--version"])
    out = capsys.readouterr().out.strip()
    assert pkg.__version__ in out
    assert rc == 0
PY

# 4) 重新安裝 editable
python -m pip -q install -e . >/dev/null

# 5) Lint（使用新版設定；不額外帶 --ignore）
echo "— Ruff（src/）—"
ruff check src --fix --config ruff.toml

# 6) 測試
echo "— Pytest —"
pytest

# 7) CLI sanity
echo "— CLI sanity —"
python -S -m smart_mail_agent.cli.sma --version

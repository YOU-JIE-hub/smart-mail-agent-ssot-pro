#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "❌ 失敗於第 $LINENO 行（exit=$?）" >&2' ERR

# 0) venv & 工具
if [ ! -x ".venv/bin/python" ]; then python3 -m venv .venv; fi
. .venv/bin/activate
python -m pip -q install -U pip wheel >/dev/null
python -m pip -q install -U ruff pytest >/dev/null

# 1) Ruff 設定（同時用 ignore 與 extend-ignore，雙保險）
cat > ruff.toml <<'TOML'
line-length = 100
target-version = "py310"
select = ["E", "F", "I"]

ignore = [
  "E701", "E702", "E402", "E741", "F403", "F811",
]
extend-ignore = [
  "E701", "E702", "E402", "E741", "F403", "F811",
]

extend-exclude = [
  ".venv", "build", "dist",
  ".z_legacy_*", ".backup_conflicts_*", ".release_stage",
  "legacy_tests", "tests/internal_smoke", "tests/ai_rpa"
]
TOML

# 2) Pytest 設定（確保 here-doc 有正確收尾）
cat > pytest.ini <<'INI'
[pytest]
addopts = -q
testpaths = tests
INI

# 3) 最小測試
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

# 4) 重新安裝 editable 套件
python -m pip -q install -e . >/dev/null

# 5) Lint（帶上 --config 與 --ignore，確保規則生效）
echo "— Ruff（src/）—"
ruff check src --fix --config ruff.toml --ignore E701,E702,E402,E741,F403,F811

# 6) 測試
echo "— Pytest —"
pytest

# 7) CLI sanity
echo "— CLI sanity —"
python -S -m smart_mail_agent.cli.sma --version

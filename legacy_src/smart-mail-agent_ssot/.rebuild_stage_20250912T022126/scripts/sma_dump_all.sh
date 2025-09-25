#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/triage/$TS"
mkdir -p "$OUT"
echo "[OUT] $OUT"

# 2.1 版本 & 環境
{
  python -V
  uname -a
  printf "PYTHONPATH=%s\n" "$PYTHONPATH"
} > "$OUT/env.txt" 2>&1 || true

# 2.2 Lint（完整輸出到檔）
ruff --version > "$OUT/ruff_version.txt" 2>&1 || true
ruff check src tests --exit-zero > "$OUT/ruff_full.txt" 2>&1 || true
# 若支援 JSON 格式，順帶一份機器可讀
ruff check src tests --exit-zero --output-format json > "$OUT/ruff_full.json" 2>/dev/null || true

# 2.3 測試（含 JUnit）
pytest -q > "$OUT/pytest.txt" 2>&1 || true
pytest -q -rA --disable-warnings --junitxml="$OUT/pytest_junit.xml" > "$OUT/pytest_verbose.txt" 2>&1 || true

# 2.4 安全檢查
bandit -q -r src -f json -o "$OUT/bandit.json" || true
pip-audit -q -f json -o "$OUT/pip_audit.json" || true

# 2.5 Alembic 升版日誌（不阻斷）
alembic upgrade head > "$OUT/alembic_upgrade.txt" 2>&1 || true

# 2.6 RAG 與 Pipeline（不出網）
python -m smart_mail_agent.cli.rag_build > "$OUT/rag_build.txt" 2>&1 || true
python -m smart_mail_agent.pipeline.pipe_run --inbox samples > "$OUT/pipe_run.txt" 2>&1 || true

# 2.7 收集現有狀態檔
cp -f reports_auto/status/ACTIONS_*.jsonl "$OUT/" 2>/dev/null || true
cp -f reports_auto/status/PIPE_SUMMARY_*.json "$OUT/" 2>/dev/null || true
cp -f reports_auto/status/DB_AUDIT_*.md "$OUT/" 2>/dev/null || true
cp -f reports_auto/logs/LAST_CRASH_PATH.txt "$OUT/" 2>/dev/null || true

# 2.8 打包
( cd "$(dirname "$OUT")" && zip -qr "$(basename "$OUT").zip" "$(basename "$OUT")" )
echo "[ZIP] $OUT.zip"

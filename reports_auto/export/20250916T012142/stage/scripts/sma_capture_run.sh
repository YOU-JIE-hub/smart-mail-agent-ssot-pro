#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/capture/$TS"
mkdir -p "$OUT"

# 進環境
. .venv_clean/bin/activate 2>/dev/null || true

# 環境資訊
{
  echo "[pwd] $(pwd)"
  python -V
  uname -a
  echo "PYTHONPATH=${PYTHONPATH:-}"
  pip freeze
} > "$OUT/env.txt" 2>&1 || true

# 小工具：執行一個步驟並把 stdout+stderr 全存檔；失敗時寫 exit code
run_step () {
  local name="$1"; shift
  echo "[RUN] $name"
  ( "$@" ) >"$OUT/${name}.txt" 2>&1 || echo $? >"$OUT/${name}.exit"
}

# 1) DB migration
run_step alembic_upgrade alembic upgrade head

# 2) 本地 CI Gate（你已經有 scripts/sma_ci_security.sh）
run_step ci_security bash scripts/sma_ci_security.sh

# 3) 死信重試
run_step retry_dead_letters python -m smart_mail_agent.cli.retry_dead_letters --batch 10 --max_attempts 3

# 4)（可選）多存一份 pipeline / rag log，方便我看
run_step rag_build   python -m smart_mail_agent.cli.rag_build
run_step pipe_run    python -m smart_mail_agent.pipeline.pipe_run --inbox samples

# 打包
( cd reports_auto/capture && zip -qr "${TS}.zip" "$TS" )
echo "[ZIP] $ROOT/reports_auto/capture/${TS}.zip"
echo "[DIR] $ROOT/$OUT"

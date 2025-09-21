#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT"
# 先進環境（相容層）
source .sma_tools/env_guard.sh || true
guard::venv_on || true

# 預設輸出根目錄（可由外部覆寫 SMA_OUT_ROOT）
export SMA_OUT_ROOT="${SMA_OUT_ROOT:-reports_auto/e2e_mail}"

python -X faulthandler -m smart_mail_agent.cli.e2e_safe || true
echo "[SAFE] 完成安全執行；輸出根在：${SMA_OUT_ROOT}"

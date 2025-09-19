#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"
OUT="${1:-/tmp}"
mkdir -p "$OUT"
CAT="$OUT/CRON_ENTRY.txt"
{
echo "# 每日 02:00 以 .venv 執行安全 E2E（請確認 SMA_EML_DIR 已指向實際郵件資料夾）"
echo "0 2 * * * SMA_ROOT=${ROOT} OFFLINE=0 SMA_EML_DIR=/abs/path/to/your_eml_dir \"
echo " /bin/bash -lc 'cd ${ROOT} && . .venv/bin/activate && scripts/sma_e2e_all_safe.sh >> reports_auto/logs/CRON_E2E.log 2>&1'"
} > "$CAT"
echo "[OK] 已輸出 cron 樣板到: $CAT"

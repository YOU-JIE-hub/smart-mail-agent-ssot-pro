#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT"
source .sma_tools/env_guard.sh
guard::at_root
guard::venv_on
: "${SMA_EML_DIR:?SMA_EML_DIR 未設定（請指向含 .eml 的資料夾）}"
bash scripts/sma_e2e_mail.sh "$SMA_EML_DIR"

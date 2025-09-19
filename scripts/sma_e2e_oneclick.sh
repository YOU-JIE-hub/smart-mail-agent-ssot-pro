#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1090
source .sma_tools/env_guard.sh
echo "[1/5] 整併 artifacts_prod…"; scripts/sma_fix_artifacts.sh
echo "[2/5] DB 遷移與視圖建立…"; python scripts/sma_db_migrate.py
echo "[3/5] 健康檢查…"; AUDIT_PATH=$(scripts/sma_project_audit.sh | tail -n1); echo "[INFO] Audit: ${AUDIT_PATH}"
echo "[4/5] 執行 E2E…"; scripts/sma_e2e_mail.sh "${1:-data/demo_eml}"
echo "[5/5] 完成。"

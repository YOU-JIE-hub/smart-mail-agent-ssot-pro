#!/usr/bin/env bash
set -Eeuo pipefail
source .sma_tools/env_guard.sh
echo "=== SMA Doctor ==="
echo "[ENV] OFFLINE=${OFFLINE:-unset}"
echo "[ENV] PYTHONPATH=$PYTHONPATH"
check(){ [[ -e "$1" ]] && echo "[OK] $1" || echo "[MISS] $1"; }
check artifacts_prod/model_pipeline.pkl
check artifacts_prod/ens_thresholds.json
check artifacts/intent_pro_cal.pkl
check reports_auto/intent_thresholds.json
if [[ -d kie ]]; then
  echo "[OK] KIE: kie/"
elif [[ -d reports_auto/kie/kie ]]; then
  echo "[OK] KIE: reports_auto/kie/kie/"
else
  echo "[MISS] KIE 權重資料夾（kie/ 或 reports_auto/kie/kie/）"
fi
echo "[INFO] E2E 腳本："; ls -l scripts/sma_e2e_mail.sh || true
echo "==============="

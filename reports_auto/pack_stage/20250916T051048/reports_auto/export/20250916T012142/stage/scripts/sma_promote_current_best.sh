#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot

# Intent：用 v11b 當穩定版
if [ -f artifacts_prod/intent_rules_calib_v11b.json ]; then
  cp -f artifacts_prod/intent_rules_calib_v11b.json artifacts_prod/intent_rules_calib.json
fi

# Spam：採用 F1 最佳的 0.405（若想保守取 0.440 也行）
mkdir -p artifacts_prod
jq -n '{spam:0.405}' > artifacts_prod/ens_thresholds.json

# KIE：啟用 hybrid_v4，暫時關掉 SLA 自動落盤（轉人工）
cat > artifacts_prod/kie_runtime_config.json <<'JSON'
{
  "kie_mode": "hybrid_v4",
  "labels": { "amount": true, "date_time": true, "env": true, "sla": false }
}
JSON

echo "[OK] Promoted: intent=v11b, spam.threshold=0.405, kie=hybrid_v4 (SLA->HIL)."

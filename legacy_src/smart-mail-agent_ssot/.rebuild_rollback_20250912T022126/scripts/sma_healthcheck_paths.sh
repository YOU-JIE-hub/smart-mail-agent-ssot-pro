#!/usr/bin/env bash
set -euo pipefail
echo "== Healthcheck: key files =="
reqs=(
  scripts/sma_dump_all_data_masked_v2.sh
  scripts/sma_e2e_mail.sh
  scripts/e2e_mail_runner.py
  artifacts_prod/ens_thresholds.json
)
for f in "${reqs[@]}"; do
  if [ -f "$f" ]; then
    printf "[OK] %s (%s bytes)\n" "$f" "$(stat -c%s "$f")"
  else
    printf "[MISS] %s\n" "$f"
  fi
done
echo "== Existing final_dump dirs =="
ls -td reports_auto/final_dump/*/ 2>/dev/null | head -n3 || echo "(none)"

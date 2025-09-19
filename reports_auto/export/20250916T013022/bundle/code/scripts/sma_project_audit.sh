#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1090
source .sma_tools/env_guard.sh

TS=$(date +"%Y%m%dT%H%M%S")
OUT="reports_auto/status/PROJECT_AUDIT_${TS}.md"

{
echo "# PROJECT AUDIT ${TS}"
echo
echo "## Artifacts"
for f in artifacts_prod/model_pipeline.pkl artifacts_prod/ens_thresholds.json artifacts_prod/intent_rules_calib_v11c.json; do
  if [ -f "$f" ]; then
    sha=$(sha256sum "$f" | awk '{print $1}')
    echo "- [OK] $f  sha256=$sha"
  else
    echo "- [MISS] $f  << 將工件置於此路徑"
  fi
done
echo
echo "## KIE runtime"
if [ -d "kie" ] || [ -d "reports_auto/kie/kie" ]; then
  echo "- KIE weights detected (hybrid 可啟用)"
else
  echo "- 無 KIE 權重，將降級 regex"
fi
echo
echo "## Database & FS"
touch "$SMA_DB_PATH" 2>/dev/null || true
if [ -f "$SMA_DB_PATH" ]; then
  size=$(stat -c%s "$SMA_DB_PATH" 2>/dev/null || echo "0")
  echo "- [OK] DB at $SMA_DB_PATH (size=${size})"
else
  echo "- [MISS] $SMA_DB_PATH 無法建立，請檢查權限"
fi
for d in reports_auto/logs reports_auto/status rpa_out/email_outbox; do
  if [ -d "$d" ] && [ -w "$d" ]; then
    echo "- [OK] dir writable: $d"
  else
    echo "- [MISS] dir not writable: $d"
  fi
done
echo
echo "## Environment"
[ -n "${OPENAI_API_KEY: "***REDACTED***"
[ -n "${SMTP_HOST:-}" ] && echo "- SMTP: configured ($SMTP_HOST:$SMTP_PORT)" || echo "- SMTP: 未設定，將使用 outbox 降級"
echo
echo "## Entry & CLI"
[ -f "src/smart_mail_agent/cli/e2e.py" ] && echo "- [OK] src/smart_mail_agent/cli/e2e.py 存在" || echo "- [MISS] 缺 src/smart_mail_agent/cli/e2e.py  << 正式入口需在此"
} > "$OUT"

echo "[OK] Audit written to $OUT"
echo "$OUT"

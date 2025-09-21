#!/usr/bin/env bash
set -Eeuo pipefail
say(){ echo "[$(date +%H:%M:%S)] $*"; }
cd "${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

RUN_DIR="$(ls -td reports_auto/e2e_mail/*/ 2>/dev/null | head -1 | sed 's:/$::')"
[ -z "$RUN_DIR" ] && { echo "[ERR] no run dir"; exit 1; }

# HIL 批次核准
tools/hil_approve_all.sh "$RUN_DIR" 2>/dev/null || true

# 可選：載入 SMTP
[ -f .env.smtp ] && . ./.env.smtp || true

# 抽檢；失敗則退為 outbox-only
set +e
scripts/sanity_precheck.sh
RC=$?
set -e
if [ $RC -ne 0 ]; then
  say "[WARN] SMTP precheck failed; fallback to outbox-only"
  export SMA_SMTP_MODE=outbox
fi

# 執行送信（尊重白名單；存在 .eml 預設不覆蓋）
python tools/send_with_intent_attachments.py --run-dir "$RUN_DIR" --to "${SMA_EMAIL_WHITELIST:-you@example.com}"
say "[DONE] SENT -> $RUN_DIR/rpa_out/email_sent"

#!/usr/bin/env bash
set -Eeuo pipefail
say(){ echo "[$(date +%H:%M:%S)] $*"; }
ROOT="${PROJ:-$HOME/projects/smart-mail-agent_ssot}"
RECIPIENT="${RECIPIENT:-h125872359@gmail.com}"
SMTP_USER="${SMTP_USER:-h125872359@gmail.com}"
SMTP_PASS="${SMTP_PASS:-ytfztoxzpjvwenun}"
SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_TLS="${SMTP_TLS:-starttls}"
FORCE_RESEND="${FORCE_RESEND:-0}"

TS="$(date +%Y%m%dT%H%M%S)"
LOG_DIR="$ROOT/reports_auto/logs/send/$TS"; mkdir -p "$LOG_DIR"
SEND_LOG="$LOG_DIR/send_${TS}.log"; ERR_LOG="$LOG_DIR/error_${TS}.log"
exec > >(tee -a "$SEND_LOG") 2> >(tee -a "$ERR_LOG" >&2)

open_path(){ # 開資料夾（WSL/Linux/mac）
  local p="$1"
  if grep -qi microsoft /proc/version 2>/dev/null; then
    command -v wslpath >/dev/null 2>&1 && explorer.exe "$(wslpath -w "$p")" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$p" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then open "$p" >/dev/null 2>&1 || true
  fi
}

trap 'code=$?; say "[ERR] exit $code — logs at $LOG_DIR"; open_path "$LOG_DIR"; exit $code' ERR

say "enter project & venv → $ROOT"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

# SMTP + 白名單
export SMA_SMTP_MODE="smtp"
export SMA_SMTP_HOST="$SMTP_HOST"
export SMA_SMTP_PORT="$SMTP_PORT"
export SMA_SMTP_USER="$SMTP_USER"
export SMA_SMTP_PASS="$SMTP_PASS"
export SMA_SMTP_TLS="$SMTP_TLS"
export SMA_EMAIL_WHITELIST="$RECIPIENT"
export SMA_ACTION_CAP_SEND_EMAIL=500

say "SMTP quick login test as $SMA_SMTP_USER"
python - <<'PY'
import os, smtplib, ssl
h=os.getenv("SMA_SMTP_HOST"); p=int(os.getenv("SMA_SMTP_PORT")); u=os.getenv("SMA_SMTP_USER"); pw=os.getenv("SMA_SMTP_PASS")
srv=smtplib.SMTP(h,p,timeout=20); srv.ehlo(); srv.starttls(context=ssl.create_default_context()); srv.login(u,pw); srv.quit()
print("[OK] SMTP login")
PY

# 取最新批（若沒有就跑一批）
say "ensure a run exists"
if ! RUN_DIR="$(ls -td reports_auto/e2e_mail/* 2>/dev/null | head -n1)"; then
  bash tools/one_click_enterprise.sh
  RUN_DIR="$(ls -td reports_auto/e2e_mail/* | head -n1)"
fi
RUN_TS="$(basename "$RUN_DIR")"
export RUN_DIR RUN_TS
say "RUN_DIR=$RUN_DIR  RUN_TS=$RUN_TS"

# 直接寄（依意圖自動掛附件；FORCE_RESEND=1 強制重寄）
say "send with intent-based attachments → $RECIPIENT $( [ "$FORCE_RESEND" = "1" ] && echo '[force]' )"
python tools/send_with_intent_attachments.py --run-dir "$RUN_DIR" --to "$RECIPIENT" $( [ "$FORCE_RESEND" = "1" ] && echo --force )

# 成果列印 + 開資料夾
say "EML files:"
ls -1 "$RUN_DIR"/rpa_out/email_sent/*.eml 2>/dev/null || echo "(no .eml)"
say "OPEN folder with logs & sent emails"
open_path "$RUN_DIR/rpa_out/email_sent"
open_path "$LOG_DIR"
say "DONE → $RUN_DIR"

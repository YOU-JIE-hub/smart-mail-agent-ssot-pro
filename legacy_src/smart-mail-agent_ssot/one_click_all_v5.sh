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
FORCE_RESEND="${FORCE_RESEND:-0}"   # 1=重寄（即便 .eml 已存在）

TS="$(date +%Y%m%dT%H%M%S)"
LOG_DIR="$ROOT/reports_auto/logs/send/$TS"
mkdir -p "$LOG_DIR"
SEND_LOG="$LOG_DIR/send_${TS}.log"
ERR_LOG="$LOG_DIR/error_${TS}.log"

# 同步輸出到檔案
exec > >(tee -a "$SEND_LOG") 2> >(tee -a "$ERR_LOG" >&2)

open_path(){
  local p="$1"
  if grep -qi microsoft /proc/version 2>/dev/null; then
    command -v wslpath >/dev/null 2>&1 && explorer.exe "$(wslpath -w "$p")" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$p" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then open "$p" >/dev/null 2>&1 || true
}

on_err(){
  code=$?
  echo "[ERR] exit code=${code} → 錯誤日誌：$ERR_LOG"
  open_path "$LOG_DIR" || true
  exit $code
}
trap on_err ERR

say "enter project & venv → $ROOT"
cd "$ROOT"
[ -f .venv/bin/activate ] && . ./.venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

# SMTP env（含白名單→只允許寄你自己）
export SMA_SMTP_MODE="smtp"
export SMA_SMTP_HOST="$SMTP_HOST"
export SMA_SMTP_PORT="$SMTP_PORT"
export SMA_SMTP_USER="$SMTP_USER"
export SMA_SMTP_PASS="$SMTP_PASS"
export SMA_SMTP_TLS="$SMTP_TLS"
export SMA_EMAIL_WHITELIST="$RECIPIENT"
export SMA_ACTION_CAP_SEND_EMAIL=200

say "SMTP quick login test as $SMTP_USER"
python - <<'PY'
import os, smtplib, ssl
h=os.getenv("SMA_SMTP_HOST","smtp.gmail.com")
p=int(os.getenv("SMA_SMTP_PORT") or "587")  # 防 None
u=os.getenv("SMA_SMTP_USER"); pw=os.getenv("SMA_SMTP_PASS")
srv=smtplib.SMTP(h,p,timeout=20); srv.ehlo()
if os.getenv("SMA_SMTP_TLS","starttls").lower()=="starttls":
    srv.starttls(context=ssl.create_default_context())
if u and pw: srv.login(u,pw)
srv.quit()
print("[OK] SMTP login")
PY

# 取最新批；若沒有就嘗試跑一批（若工具不存在則略過）
say "ensure a run exists"
if ! RUN_DIR="$(ls -td reports_auto/e2e_mail/* 2>/dev/null | head -n1)"; then
  if [ -x tools/one_click_enterprise.sh ]; then
    bash tools/one_click_enterprise.sh
    RUN_DIR="$(ls -td reports_auto/e2e_mail/* | head -n1)"
  else
    echo "[WARN] no run found and one_click_enterprise.sh not present; please generate a batch first."
    exit 1
  fi
fi
RUN_TS="$(basename "$RUN_DIR")"
export RUN_DIR RUN_TS
say "RUN_DIR=$RUN_DIR  RUN_TS=$RUN_TS"

# 可選：HIL 全核准 / materialize（若腳本不存在就 no-op）
say "HIL approve-all for SendEmail (if any)"
[ -x tools/hil_approve_all.sh ] && bash tools/hil_approve_all.sh "$RUN_TS" SendEmail || echo "[HIL] (no-op)"
say "materialize placeholders + backfill DB + refresh summary"
[ -x tools/materialize_and_refresh.sh ] && bash tools/materialize_and_refresh.sh "$RUN_TS" || echo "[MATERIALIZE] (no-op)"

say "send with intent-based attachments → $RECIPIENT"
python tools/send_with_intent_attachments.py --run-dir "$RUN_DIR" --to "$RECIPIENT" $( [ "$FORCE_RESEND" = "1" ] && echo --force )

# 快速列出狀態與 EML
say "DB snapshot (SendEmail for this run)"
sqlite3 db/sma.sqlite "
  SELECT case_id, COALESCE(action_type,action) AS type, status
  FROM actions
  WHERE run_ts='$RUN_TS' AND COALESCE(action_type,action)='SendEmail';
"
say "EML files:"
ls -1 "$RUN_DIR"/rpa_out/email_sent/*.eml 2>/dev/null || echo "(no .eml)"

say "OPEN folder with logs & sent emails"
open_path "$LOG_DIR" || true

say "DONE → $RUN_DIR"

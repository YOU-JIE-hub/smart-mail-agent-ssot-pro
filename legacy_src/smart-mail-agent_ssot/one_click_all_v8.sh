#!/usr/bin/env bash
set -Eeuo pipefail
say(){ echo "[$(date +%H:%M:%S)] $*"; }

# ===== 可調參數（可用環境變數覆蓋）=====
ROOT="${PROJ:-$HOME/projects/smart-mail-agent_ssot}"
RECIPIENT="${RECIPIENT:-h125872359@gmail.com}"
SMTP_USER="${SMTP_USER:-h125872359@gmail.com}"
SMTP_PASS="${SMTP_PASS:-ytfztoxzpjvwenun}"   # 你的 Gmail App Password
SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_TLS="${SMTP_TLS:-starttls}"
FORCE_RESEND="${FORCE_RESEND:-0}"           # 1=強制重寄
RUN_SANITY_EMAIL="${RUN_SANITY_EMAIL:-0}"   # 1=順便寄一封驗證信

# ===== 日誌與錯誤檔 =====
TS="$(date +%Y%m%dT%H%M%S)"
LOG_DIR="$ROOT/reports_auto/logs/send/$TS"
mkdir -p "$LOG_DIR"
SEND_LOG="$LOG_DIR/send_${TS}.log"
ERR_LOG="$LOG_DIR/error_${TS}.log"

# 將 stdout/stderr 同步進檔
exec > >(tee -a "$SEND_LOG") 2> >(tee -a "$ERR_LOG" >&2)

# 跨平台開資料夾（WSL/Linux/mac）
open_path(){
  local p="$1"
  if grep -qi microsoft /proc/version 2>/dev/null; then
    command -v wslpath >/dev/null 2>&1 && explorer.exe "$(wslpath -w "$p")" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$p" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$p" >/dev/null 2>&1 || true
  fi
}

on_error(){
  code=$?
  say "[ERROR] script failed (exit=$code). Logs at: $LOG_DIR"
  open_path "$LOG_DIR"
  exit $code
}
trap on_error ERR

say "enter project & venv → $ROOT"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"
export SMA_SMTP_MODE="smtp"
export SMA_SMTP_HOST="$SMTP_HOST" SMA_SMTP_PORT="$SMTP_PORT" SMA_SMTP_USER="$SMTP_USER" SMA_SMTP_PASS="$SMTP_PASS" SMA_SMTP_TLS="$SMTP_TLS"
export SMA_EMAIL_WHITELIST="$RECIPIENT"
export SMA_ACTION_CAP_SEND_EMAIL=200

say "verify: SMTP login & env sanity"
python - <<'PY'
import os, smtplib, ssl
h=os.getenv("SMA_SMTP_HOST"); p=int(os.getenv("SMA_SMTP_PORT")); u=os.getenv("SMA_SMTP_USER"); pw=os.getenv("SMA_SMTP_PASS"); tls=os.getenv("SMA_SMTP_TLS","starttls")
srv=smtplib.SMTP(h,p,timeout=20); srv.ehlo()
if tls.lower()=="starttls": srv.starttls(context=ssl.create_default_context())
if u: srv.login(u,pw)
srv.quit()
print("[OK] SMTP verified")
PY

# 取 run 目錄，沒有就試著跑一次 enterprise
say "ensure a run exists"
if ! RUN_DIR="$(ls -td reports_auto/e2e_mail/* 2>/dev/null | head -n1)"; then
  if [ -x tools/one_click_enterprise.sh ]; then
    bash tools/one_click_enterprise.sh
    RUN_DIR="$(ls -td reports_auto/e2e_mail/* | head -n1)"
  else
    say "[WARN] no run found and tools/one_click_enterprise.sh missing; creating skeleton"
    RUN_DIR="reports_auto/e2e_mail/$TS"; mkdir -p "$RUN_DIR/rpa_out/email_outbox" "$RUN_DIR/rpa_out/email_sent"
    echo -e "Subject: Hello\n\nBody." > "$RUN_DIR/rpa_out/email_outbox/$TS.txt"
  fi
fi
RUN_TS="$(basename "$RUN_DIR")"
export RUN_DIR RUN_TS
say "RUN_DIR=$RUN_DIR  RUN_TS=$RUN_TS"

# （可選）HIL 全核准
say "HIL approve-all for SendEmail (if any)"
if [ -x tools/hil_approve_all.sh ]; then
  bash tools/hil_approve_all.sh "$RUN_TS" "SendEmail" || true
else
  say "[HIL] (no-op) approve-all for SendEmail if any"
fi

# （可選）補材/回填/刷新
say "materialize placeholders + backfill DB + refresh summary"
if [ -x tools/materialize_and_refresh.sh ]; then
  bash tools/materialize_and_refresh.sh "$RUN_TS" || true
else
  say "[MATERIALIZE] (no-op) placeholders/backfill/summary refresh"
fi

# 主寄送（意圖附檔）
say "send with intent-based attachments → $RECIPIENT"
python tools/send_with_intent_attachments.py --run-dir "$RUN_DIR" --to "$RECIPIENT" $( [ "$FORCE_RESEND" = "1" ] && echo "--force" )

# 驗證寄信（可選）
if [ "$RUN_SANITY_EMAIL" = "1" ]; then
  say "send sanity UTF-8 + attachment test → $RECIPIENT"
  python tools/sanity_send.py --to "$RECIPIENT"
fi

# DB snapshot（若有 DB）
say "DB snapshot (SendEmail for this run)"
if [ -f db/sma.sqlite ]; then
  sqlite3 db/sma.sqlite "SELECT case_id, COALESCE(action_type,action), status, payload_ref FROM actions WHERE run_ts='$RUN_TS' AND COALESCE(action_type,action)='SendEmail';" || true
else
  say "(no db/sma.sqlite)"
fi

# 列出 .eml
say "EML files:"
ls -1 "$RUN_DIR"/rpa_out/email_sent/*.eml 2>/dev/null || echo "(no .eml)"

# 完成 & 開資料夾
say "OPEN folder with logs & sent emails"
open_path "$RUN_DIR"
open_path "$LOG_DIR"
say "DONE → $RUN_DIR"

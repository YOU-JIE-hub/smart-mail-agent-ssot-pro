#!/usr/bin/env bash
set -Eeuo pipefail
HOST="${SMA_SMTP_HOST:-smtp.gmail.com}"
PORT="${SMA_SMTP_PORT:-587}"
TLS="${SMA_SMTP_TLS:-starttls}"
USER="${SMA_SMTP_USER:-}"
PASS="${SMA_SMTP_PASS:-}"
python - <<PY
import os, smtplib, sys
host=os.getenv("SMA_SMTP_HOST","smtp.gmail.com")
port=int(os.getenv("SMA_SMTP_PORT","587"))
tls=os.getenv("SMA_SMTP_TLS","starttls")
user=os.getenv("SMA_SMTP_USER","")
pwd =os.getenv("SMA_SMTP_PASS","")
try:
    s=smtplib.SMTP(host, port, timeout=20)
    if tls=="starttls":
        s.starttls()
    if user and pwd:
        s.login(user, pwd)
    s.noop(); s.quit()
    print("[OK] SMTP precheck passed")
    sys.exit(0)
except Exception as e:
    print("[FAIL] SMTP precheck:", repr(e))
    sys.exit(1)
PY

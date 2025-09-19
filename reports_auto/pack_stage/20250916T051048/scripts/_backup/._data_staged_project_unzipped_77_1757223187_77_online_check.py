from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

__all__ = ["main", "smtplib"]


def main() -> int:
    need = ["SMTP_USER", "SMTP_PASS", "SMTP_HOST", "SMTP_PORT", "REPLY_TO"]
    env = {k: os.getenv(k) for k in need}
    if any(not env[k] for k in need):
        return 2
    msg = EmailMessage()
    msg["From"] = env["REPLY_TO"]
    msg["To"] = env["REPLY_TO"]
    msg["Subject"] = "Online check"
    msg.set_content("ping")
    try:
        with smtplib.SMTP_SSL(env["SMTP_HOST"], int(env["SMTP_PORT"])) as s:
            s.login(env["SMTP_USER"], env["SMTP_PASS"])
            s.send_message(msg)
        return 0
    except Exception:
        return 1

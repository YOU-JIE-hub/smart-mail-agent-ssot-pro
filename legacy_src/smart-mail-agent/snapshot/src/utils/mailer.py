from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Optional


def validate_smtp_config() -> bool:
    req = ["SMTP_USER", "SMTP_PASS", "SMTP_HOST", "SMTP_PORT", "SMTP_FROM"]
    for k in req:
        if not os.getenv(k):
            return False
    try:
        int(os.getenv("SMTP_PORT", ""))
    except Exception:
        return False
    return True


def send_email_with_attachment(
    recipient: str,
    subject: str,
    body_html: str,
    attachment_path: Optional[str | Path] = None,
) -> bool:
    msg = EmailMessage()
    msg["To"] = recipient
    msg["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "no-reply@example.com"))
    msg["Subject"] = subject
    msg.set_content("This is a MIME alternative message.")
    msg.add_alternative(body_html or "", subtype="html")

    if attachment_path:
        p = Path(attachment_path)
        data = p.read_bytes()
        msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=p.name)

    host = os.getenv("SMTP_HOST", "localhost")
    port = int(os.getenv("SMTP_PORT", "465"))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")

    with smtplib.SMTP_SSL(host, port) as s:
        if user and pwd:
            s.login(user, pwd)
        s.send_message(msg)

    return True

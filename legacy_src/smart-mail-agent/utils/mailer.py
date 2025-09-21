from __future__ import annotations

import os
import pathlib
import smtplib
from email.message import EmailMessage


def _require_env(name: str) -> str:
    v = os.getenv(name, "")
    if not v:
        raise ValueError("SMTP 設定錯誤")
    return v


def validate_smtp_config() -> None:
    _require_env("SMTP_USER")
    _require_env("SMTP_PASS")
    _require_env("SMTP_HOST")
    _require_env("SMTP_PORT")


def send_email_with_attachment(
    *, recipient: str, subject: str, body_html: str, attachment_path: str
) -> bool:
    p = pathlib.Path(attachment_path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    # 不再因 OFFLINE 直接返回；測試會 mock smtplib.SMTP_SSL
    validate_smtp_config()
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "0"))
    sender = os.getenv("SMTP_FROM", user)

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body_html or "", subtype="html")
    msg.add_attachment(
        p.read_bytes(), maintype="application", subtype="octet-stream", filename=p.name
    )

    with smtplib.SMTP_SSL(host, port) as s:
        s.login(user, pwd)
        s.send_message(msg)
    return True

import email
import imaplib
from datetime import datetime
from email import policy
from typing import Any


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def pull_imap(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    host = cfg.get("host")
    user = cfg.get("user")
    pwd = cfg.get("pass")
    box = cfg.get("mailbox", "INBOX")
    use_ssl = bool(cfg.get("ssl", True))
    port = int(cfg.get("port") or (993 if use_ssl else 143))
    mails: list[dict[str, Any]] = []
    if not host or not user or not pwd:
        return mails
    M = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
    M.login(user, pwd)
    M.select(box)
    typ, data = M.search(None, "ALL")
    ids = data[0].split()[:50]
    for i in ids:
        typ, msg_data = M.fetch(i, "(RFC822)")
        if typ != "OK":
            continue
        msg = email.message_from_bytes(msg_data[0][1], policy=policy.default)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_content()
                    break
        else:
            body = msg.get_content()
        mails.append(
            {
                "id": str(i.decode()),
                "subject": msg.get("Subject"),
                "sender": msg.get("From"),
                "body": body or "",
                "ts": _now(),
            }
        )
    M.close()
    M.logout()
    return mails

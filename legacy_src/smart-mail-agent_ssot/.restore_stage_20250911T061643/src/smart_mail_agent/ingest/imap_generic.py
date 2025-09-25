from __future__ import annotations

import email
import imaplib
from collections.abc import Iterable


def from_imap(host: str, user: str, password: str, folder: str = "INBOX") -> Iterable[dict]:
    M = imaplib.IMAP4_SSL(host)
    try:
        M.login(user, password)
        M.select(folder)
        typ, data = M.search(None, "ALL")
        for num in data[0].split()[:100]:
            typ, msg_data = M.fetch(num, "(RFC822)")
            if typ != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subject = msg.get("Subject", "")
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")
            yield {"id": num.decode(), "subject": subject, "body": body}
    finally:
        try:
            M.logout()
        except Exception:
            pass

from __future__ import annotations

from email.message import EmailMessage

Attachment = tuple[str, bytes]


def render_mime(
    to: str,
    subj: str,
    body: str,
    attachments: list[Attachment] | None = None,
    sender: str | None = None,
) -> bytes:
    msg = EmailMessage()
    if sender:
        msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subj
    msg.set_content(body or "")
    for name, data in attachments or []:
        msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
    return msg.as_bytes()

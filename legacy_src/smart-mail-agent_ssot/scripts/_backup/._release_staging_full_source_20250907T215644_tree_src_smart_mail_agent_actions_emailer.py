from typing import Any

from smart_mail_agent.transport.mail import render_mime
from smart_mail_agent.transport.smtp_send import send_smtp


def send_answer(to: str, subject: str, body: str, attachments: list[tuple[str, bytes]] | None = None) -> dict[str, Any]:
    mime = render_mime(to=to, subj=subject, body=body, attachments=attachments or [])
    return send_smtp(mime)

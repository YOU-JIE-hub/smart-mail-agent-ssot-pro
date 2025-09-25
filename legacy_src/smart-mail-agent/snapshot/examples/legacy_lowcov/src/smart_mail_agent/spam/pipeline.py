from __future__ import annotations

from typing import Any

from .rules import label_email


def analyze(email: dict[str, Any]) -> dict[str, Any]:
    sender = email.get("sender", "") or ""
    subject = email.get("subject", "") or ""
    content = email.get("content", "") or ""
    attachments = email.get("attachments") or []
    label, score, reasons = label_email(sender, subject, content, attachments)
    return {"label": label, "score": int(score), "reasons": list(reasons), "subject": subject}

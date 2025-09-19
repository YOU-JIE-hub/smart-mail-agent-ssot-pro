from __future__ import annotations

from typing import Any

from smart_mail_agent.actions.pdf import render_quote_pdf
from smart_mail_agent.actions.quote import build_quote


def route(mail: dict[str, Any], intent: str, kie: dict[str, Any] | None = None) -> dict[str, Any]:
    artifacts: list[str] = []
    outbox: list[str] = []
    needs = False
    if intent == "quote":
        qr = build_quote(mail, kie or {})
        artifacts.append(qr["quote_path"])
        pdf = render_quote_pdf(qr["quote"])
        if pdf.get("ok"):
            artifacts.append(pdf["pdf_path"])
    elif intent == "invoice":
        needs = True
    else:
        needs = True
    return {"artifacts": artifacts, "outbox": outbox, "needs_review": needs}

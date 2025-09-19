from __future__ import annotations

from typing import Any

from smart_mail_agent.actions.emailer import send_answer
from smart_mail_agent.actions.faq import run_faq
from smart_mail_agent.actions.pdf import render_quote_pdf
from smart_mail_agent.actions.quote import build_quote
from smart_mail_agent.utils.config import paths


def run_action(mail: dict[str, Any], intent: str, kie: dict[str, Any] | None = None) -> dict[str, Any]:
    p = paths()
    artifacts: list[str] = []
    outbox: list[str] = []

    if intent == "faq":
        question = mail.get("body") or mail.get("subject") or "常見問題"
        faq = run_faq(question)
        artifacts.append(faq["answer_path"])
    elif intent in {"quote", "invoice"}:
        qr = build_quote(mail, kie or {})
        artifacts.append(qr["quote_path"])
        pdf = render_quote_pdf(qr["quote"])
        if pdf.get("ok"):
            artifacts.append(pdf["pdf_path"])
    else:
        ack = p.status / f"answer_ack_{mail.get('id')}.md"
        ack.write_text(
            f"您好，已收到您的訊息：\n\n{mail.get('body')}\n\n我們將儘速回覆。",
            encoding="utf-8",
        )
        artifacts.append(str(ack))

    res = send_answer(
        to="customer@example.com",
        subject=f"[回覆]{intent}",
        body="系統自動回覆，詳見附件或平台紀錄。",
        attachments=[],
    )
    if res.get("eml"):
        outbox.append(res["eml"])

    return {"ok": True, "artifacts": artifacts, "outbox": outbox}

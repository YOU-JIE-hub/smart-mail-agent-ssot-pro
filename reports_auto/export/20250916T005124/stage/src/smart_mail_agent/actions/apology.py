from __future__ import annotations

from typing import Any

from .emailer import send_answer
from .types import ActionContext

TEMPLATE = "您好，針對您反映的問題，我們深感抱歉。已建立追蹤並優先處理。如需補充資訊，請直接回覆此信。"


def send_apology(ctx: ActionContext, to: str, mail_id: str, key: str) -> dict[str, Any]:
    subject = f"[致歉與協助] 來信 {mail_id}"
    res = send_answer(to=to, subject=subject, body=TEMPLATE, attachments=None)
    return {"ok": True, "eml": res.get("eml")}

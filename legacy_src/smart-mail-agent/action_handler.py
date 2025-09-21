from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from smart_mail_agent.smart_mail_agent.utils.pdf_safe import write_pdf_or_txt


def _mk_reply(
    subject_tag: str, action: str, attachments: List[str] | None = None
) -> Dict[str, Any]:
    return {
        "ok": True,
        "action_name": action,
        "subject": subject_tag,
        "attachments": attachments or [],
    }


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    label = payload.get("predicted_label", "")
    subj = payload.get("subject") or payload.get("content") or ""
    # 六大分類（中文）
    if label == "請求技術支援":
        return _mk_reply("[支援回覆] " + subj, "reply_support")
    if label == "申請修改資訊":
        return _mk_reply("[資料更新受理] " + subj, "apply_info_change")
    if label == "詢問流程或規則":
        return _mk_reply("[流程說明] " + subj, "reply_faq")
    if label == "投訴與抱怨":
        return _mk_reply("[致歉回覆] " + subj, "reply_apology")
    if label == "業務接洽或報價":
        Path("data/output").mkdir(parents=True, exist_ok=True)
        p = write_pdf_or_txt(["Quote"], Path("data/output"), "quote")
        return _mk_reply("[報價] " + subj, "send_quote", [p])
    # 其他
    return _mk_reply("[自動回覆] " + subj, "reply_general")

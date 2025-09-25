from __future__ import annotations

from typing import Any, Dict

ELLIPSIS = "..."


def smart_truncate(text: str, max_chars: int = 1000) -> str:
    text = text or ""
    if max_chars is None or max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    # 規則：極短上限（例如 2）→ 只輸出 "..."
    if max_chars < len(ELLIPSIS) + 1:
        return ELLIPSIS
    head = text[: max(0, max_chars - len(ELLIPSIS))]
    return f"{head}{ELLIPSIS}\n"


_KEYWORDS = {
    "sales_inquiry": ["報價", "詢價", "合作", "報價單", "價格"],
    "reply_support": ["技術支援", "無法使用", "錯誤", "bug", "故障", "當機"],
    "apply_info_change": ["修改", "變更", "更正"],
    "reply_faq": ["流程", "規則", "怎麼", "如何", "退費", "退款流程"],
    "complaint": ["投訴", "抱怨", "退款", "退貨", "很差", "惡劣"],
    "send_quote": ["寄出報價", "發送報價"],
}


def classify_intent(subject: str = "", content: str = "") -> Dict[str, Any]:
    text = f"{subject} {content}"
    for label, kws in _KEYWORDS.items():
        if any(k in text for k in kws):
            return {"label": label, "predicted_label": label, "confidence": 0.8}
    return {"label": "unknown", "predicted_label": "unknown", "confidence": 0.0}


def load_model() -> object:
    class _Dummy: ...

    return _Dummy()

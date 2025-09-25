from __future__ import annotations
from typing import List

__all__ = ["to_categories"]

ALIASES = {
    "biz_quote": ["quote","quotation","rfq","price","報價","sales"],
    "tech_support": ["support","bug","issue","故障","維修","支援","技術"],
    "complaint": ["complaint","refund","抱怨","投訴","退費"],
    "policy_qa": ["policy","faq","document","docs","規範","條款"],
    "profile_update": ["update profile","change address","更新資料","變更","profile"],
    "other": [],
}

ORDER = ["biz_quote","tech_support","complaint","policy_qa","profile_update","other"]

def to_categories(text: str) -> List[str]:
    t = (text or "").lower()
    out: List[str] = []
    for lab in ORDER:
        if any(tok in t for tok in ALIASES[lab]):
            out.append(lab)
    return out or ["other"]

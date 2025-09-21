from __future__ import annotations
from typing import Dict, Any, List

__all__ = ["analyze_text"]

KEYWORDS = {
    "biz_quote": ["quote","quotation","rfq","price","quote request","報價","報價單"],
    "tech_support": ["support","error","bug","fail","issue","help","故障","維修","報錯"],
    "complaint": ["complaint","angry","unhappy","refund","退費","抱怨","投訴"],
    "policy_qa": ["policy","faq","document","guide","規範","條款","文件"],
    "profile_update": ["update profile","change address","變更地址","更新資料","電話更改"],
}

def analyze_text(text: str, **kw) -> Dict[str, Any]:
    t = (text or "").lower()
    hits: List[str] = []
    for lab, toks in KEYWORDS.items():
        if any(tok in t for tok in toks):
            hits.append(lab)
    return {
        "ok": True,
        "length": len(text or ""),
        "hits": hits,
        "preview": text[:200],
    }

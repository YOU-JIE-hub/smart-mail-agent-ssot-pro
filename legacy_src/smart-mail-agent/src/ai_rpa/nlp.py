from __future__ import annotations
from typing import List, Dict, TypedDict
import os

# Rule-based fallback (offline-safe)
_SALES_KW   = ["合作","報價","價格","方案","洽談","quote","price"]
_SUPPORT_KW = ["客服","協助","技術","無法","錯誤","登入","bug","crash"]
_POLICY_KW  = ["規則","機制","條件","限制","refund","退款","使用限制"]
_PROFILE_KW = ["更新","修改","變更","電話","地址","email","資料","重設"]
_COMPLAINT_KW = ["投訴","抱怨","失望","延遲","不滿","很爛","糟糕"]

class NLPClassify(TypedDict):
    intents: List[str]
    labels: List[str]
    length: int

class NLPSummary(TypedDict):
    summary: str

def _match_any(text: str, kws: List[str]) -> bool:
    return any(k in text for k in kws)

def _classify_rule(text: str) -> NLPClassify:
    t = (text or "").strip()
    intents: List[str] = []
    labels: List[str] = []
    if _match_any(t, _SUPPORT_KW):
        intents.append("tech_support"); labels.append("support")
    if _match_any(t, _PROFILE_KW):
        intents.append("profile_update"); labels.append("profile_update")
    if _match_any(t, _POLICY_KW):
        intents.append("policy_qa"); labels.append("policy_qa")
    if _match_any(t, _COMPLAINT_KW):
        intents.append("complaint"); labels.append("complaint")
    if _match_any(t, _SALES_KW):
        intents.extend(["sales","quote"]); labels.append("biz_quote")
    if not intents:
        intents.append("general"); labels.append("other")
    return {"intents": intents, "labels": labels, "length": len(t.split())}

def _predict_intent(text: str) -> NLPClassify:
    """若環境指定 ML 且可用則走 ML，否則回退規則版。"""
    if os.getenv("SMA_INTENT_BACKEND","").lower() == "ml":
        try:
            from models.intent import serving_ml as _iml
            if hasattr(_iml, "available") and _iml.available():
                # _iml.predict(text) 預期回傳 {intents, labels, length}
                return _iml.predict(text)  # type: ignore[return-value]
        except Exception:
            pass
    return _classify_rule(text)

def classify(text: str) -> NLPClassify:
    return _predict_intent(text)

def summarize(text: str) -> Dict[str, str]:
    t = (text or "").strip().replace("\n"," ")
    if len(t) > 120: t = t[:117] + "..."
    return {"summary": t or ""}

def analyze_text(text: str) -> Dict[str, object]:
    """
    供 ai_rpa.main 使用的一站式分析：回傳 {intents, labels, length, summary}
    """
    c = classify(text)
    s = summarize(text)
    return {**c, **s}

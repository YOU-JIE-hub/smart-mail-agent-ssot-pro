from __future__ import annotations

from typing import Any, Dict


def smart_truncate(s: str, n: int) -> str:
    if n <= 0:
        return "..."
    return (s[: max(1, n - 1)] + "...") if len(s) > n else s


def load_model():
    # 測試會 monkeypatch 這支；預設回傳 None
    return None


def classify_intent(subject: str, body: str) -> Dict[str, Any]:
    try:
        _ = load_model()
    except Exception:
        return {"label": "unknown", "confidence": 0.0}
    text = (subject or "") + " " + (body or "")
    if any(k in text for k in ("報價", "價格", "quote", "quotation")):
        return {"label": "sales_inquiry", "confidence": 0.9}
    if any(k in text for k in ("退款", "退費", "complaint", "投訴")):
        return {"label": "complaint", "confidence": 0.8}
    if any(k in text for k in ("流程", "規則", "FAQ", "常見問題")):
        return {"label": "詢問流程或規則", "confidence": 0.85}
    return {"label": "other", "confidence": 0.2}

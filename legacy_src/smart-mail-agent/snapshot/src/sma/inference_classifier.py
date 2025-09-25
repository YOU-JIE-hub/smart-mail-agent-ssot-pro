from __future__ import annotations

from typing import Dict


def smart_truncate(s: str, n: int) -> str:
    s = s or ""
    if len(s) <= n:
        return s
    out = s[: max(0, n - 1)].rstrip()
    if not out.endswith("..."):
        out = out.rstrip(".") + "..."
    return out


def load_model():
    # 測試會 monkeypatch；保持介面即可
    return object()


def classify_intent(subject: str, content: str) -> Dict[str, str]:
    text = f"{subject or ''} {content or ''}"
    if any(k in text for k in ("報價", "詢價", "價格")):
        return {"label": "sales_inquiry"}
    if any(k in text for k in ("退款", "退貨", "抱怨", "投訴", "嚴重")):
        return {"label": "complaint"}
    return {"label": "other"}

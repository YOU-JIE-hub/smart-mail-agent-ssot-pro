from __future__ import annotations
from typing import Dict, Any

__all__ = ["route"]

# 固定映射：六類 Intent → 行為
MAP = {
    "biz_quote": "create_quote_ticket",
    "tech_support": "create_support_ticket",
    "complaint": "escalate_to_CX",
    "policy_qa": "send_policy_docs",
    "profile_update": "update_profile",
    "other": "manual_triage",
}

def _pick_label(pred: Dict[str, Any]) -> str:
    # router 鍵名兼容：final > pred > label > top
    for k in ("final","pred","label","top"):
        v = pred.get(k)
        if isinstance(v, str) and v:
            return v
    # p1/score/gap 之類資訊不會直接用於映射，留白則判 other
    return "other"

def route(pred: Dict[str, Any]) -> Dict[str, Any]:
    label = _pick_label(pred)
    action = MAP.get(label, "manual_triage")
    out = {"label": label, "action": action}
    # 把 p1/score/gap 等附帶資訊透傳，便於測試檢查
    for k in ("p1","score","gap"):
        if k in pred:
            out[k] = pred[k]
    return out

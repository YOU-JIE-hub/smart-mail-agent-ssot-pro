from __future__ import annotations
import os, importlib
from typing import Any, Dict

def _load_thresholds() -> Dict[str,float]:
    try:
        pe = importlib.import_module("tools.orch.policy_engine")
        return pe.load_thresholds()
    except Exception:
        # fallback，之後可改到 configs
        return {"報價":0.70,"投訴":0.55,"一般回覆":0.50,"規則詢問":0.55,"資料異動":0.65,"技術支援":0.55}

def plan_action(intent: str, confidence: float, email: dict, slots: dict|None=None) -> Dict[str,Any]:
    slots = slots or {}
    dry = bool(os.environ.get("SMA_DRY_RUN"))
    thr = _load_thresholds()
    def hitl(reason:str):
        return {"action":"hitl_queue","ok":False,"route":{"channel":"hitl","dry_run":dry},"required":[],
                "template":"hitl_v1","params":{"reason":reason,"intent":intent,"confidence":confidence}}
    if confidence < thr.get(intent,0.60):
        return hitl("low_confidence")

    subj = email.get("subject","") or ""
    body = email.get("body","") or ""

    if intent == "一般回覆":
        return {"action":"reply_email","ok":True,"route":{"channel":"email","dry_run":dry},
                "required":[],"template":"reply_generic.md",
                "params":{"subject":"[自動回覆] 已收到您的來信",
                          "body":"我們已收到您的來信，將盡快處理。"}}

    if intent == "規則詢問":
        return {"action":"policy_reply","ok":True,"route":{"channel":"email","dry_run":dry},
                "required":[],"template":"reply_generic.md",
                "params":{"subject":"[回覆] 政策條款","body":"依據公司政策第 X 條，回覆如下…"}}

    if intent == "投訴":
        sev = "P2" if any(k in (subj+body) for k in ["重大","緊急","法律"]) else "P3"
        return {"action":"create_ticket","ok":True,"route":{"channel":"ticket","dry_run":dry},
                "required":[],"template":"ts_v1","params":{"severity":sev,"tags":["complaint"],"summary":subj or "投訴"}}

    if intent == "技術支援":
        sev = "P2" if "TS-" in (subj+body) else "P3"
        return {"action":"create_ticket","ok":True,"route":{"channel":"ticket","dry_run":dry},
                "required":[],"template":"ts_v1","params":{"severity":sev,"tags":["tech_support"],"summary":subj or "技術支援"}}

    if intent == "資料異動":
        return {"action":"change_request","ok":True,"route":{"channel":"crm","dry_run":dry},
                "required":[],"template":"cr_v1","params":{"fields":{}, "requester":"noreply@example.com"}}

    if intent == "報價":
        # 需要 price/qty；若缺 → HITL
        miss = [k for k in ("price","qty") if slots.get(k) is None]
        if miss: return hitl("missing_slots:"+",".join(miss))
        # 若都齊 → quote_reply（由 adapter 產 PDF / TXT）
        return {"action":"quote_reply","ok":True,"route":{"channel":"email","dry_run":dry},
                "required":[],"template":"quote_email.md",
                "params":{"item": slots.get("item","N/A"),
                          "unit_price": float(slots["price"]),
                          "qty": int(slots["qty"]),
                          "subtotal": float(slots["price"])*int(slots["qty"]),
                          "tax": 0, "total": float(slots["price"])*int(slots["qty"]),
                          "currency":"TWD","valid_until":"2099-12-31",
                          "subject":"[報價單] 感謝您的詢價"}}
    return hitl("unknown_intent")

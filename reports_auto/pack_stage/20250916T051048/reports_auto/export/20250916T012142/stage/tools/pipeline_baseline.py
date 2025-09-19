from __future__ import annotations
import json, re, os
from pathlib import Path
from typing import Dict, Any
ROOT = Path(os.environ.get("ROOT") or Path.cwd())
def load_contract() -> Dict[str,Any]:
    return json.loads((ROOT/"artifacts_prod/intent_contract.json").read_text(encoding="utf-8"))
def classify_rule(email: Dict[str,Any], contract: Dict[str,Any]) -> str:
    subject=email.get("subject",""); body=email.get("body","")
    for it in contract.get("intents", []):
        name=it.get("name",""); tag=it.get("subject_tag","")
        if tag and tag in subject: return name
        if name and (name in subject or name in body): return name
    return "一般回覆"
def extract_slots_rule(email: Dict[str,Any], intent: str) -> Dict[str,Any]:
    text=f"{email.get('subject','')}\n{email.get('body','')}"
    slots={}
    m=re.search(r"(?:單價|price)[:：]\s*([0-9]+)", text);  slots["price"]=int(m.group(1)) if m else None
    m=re.search(r"(?:數量|qty)[:：]\s*([0-9]+)", text);    slots["qty"]=int(m.group(1)) if m else None
    m=re.search(r"(?:單號|order|ticket)[:：]?\s*([A-Za-z0-9-]{4,})", text); slots["id"]=m.group(1) if m else None
    return slots
def plan_actions_rule(intent: str, slots: Dict[str,Any]) -> Dict[str,Any]:
    if intent=="報價":       return {"action":"quote_reply","template":"quote_v1","required":["price","qty"],"ok": all(slots.get(k) for k in ("price","qty"))}
    if intent=="技術支援":   return {"action":"create_ticket","template":"ts_v1","required":["id"],"ok": bool(slots.get("id"))}
    if intent=="投訴":       return {"action":"escalate_cs","template":"cs_v1","required":[],"ok":True}
    if intent=="規則詢問":   return {"action":"policy_reply","template":"policy_v1","required":[],"ok":True}
    if intent=="資料異動":   return {"action":"update_record","template":"update_v1","required":["id"],"ok": bool(slots.get("id"))}
    return {"action":"generic_reply","template":"plain_v1","required":[],"ok":True}


def classify(email):
    from .pipeline_baseline import classify_rule as _c
    return _c(email)

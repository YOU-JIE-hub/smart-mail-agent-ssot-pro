from __future__ import annotations
import json, re, os, time
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(os.environ.get("ROOT") or Path.cwd())

def load_contract() -> Dict[str,Any]:
    return json.loads((ROOT/"artifacts_prod/intent_contract.json").read_text(encoding="utf-8"))

def classify_rule(email: Dict[str,Any], contract: Dict[str,Any]) -> str:
    subject = email.get("subject","") or ""
    body    = email.get("body","") or ""
    for it in contract.get("intents", []):
        name = it.get("name",""); tag = it.get("subject_tag","")
        if tag and tag in subject: return name
        if name and (name in subject or name in body): return name
    return "一般回覆"

def extract_slots_rule(email: Dict[str,Any], intent: str) -> Dict[str,Any]:
    text = f"{email.get('subject','')}\n{email.get('body','')}"
    slots = {}
    if m:=re.search(r"(?:單價|price)[:：]\s*([0-9]+)", text): slots["price"]=int(m.group(1))
    if m:=re.search(r"(?:數量|qty)[:：]\s*([0-9]+)", text):  slots["qty"]=int(m.group(1))
    if m:=re.search(r"(?:訂單|單號|order)[:：]?\s*([A-Z0-9-]{4,})", text): slots["order_id"]=m.group(1)
    return slots

def plan_rule(intent: str, slots: Dict[str,Any]) -> Dict[str,Any]:
    actions: List[Dict[str,Any]] = []
    if intent == "報價":
        actions.append({"type":"quote.generate", "price": slots.get("price", 100), "qty": slots.get("qty", 1)})
        actions.append({"type":"email.reply", "template":"quote_ok"})
    elif intent == "技術支援":
        actions.append({"type":"ticket.open", "severity":"S3"})
        actions.append({"type":"email.reply", "template":"support_ack"})
    elif intent == "投訴":
        actions.append({"type":"ticket.open", "severity":"S2"})
        actions.append({"type":"email.reply", "template":"complaint_ack"})
    elif intent == "資料異動":
        actions.append({"type":"db.update", "fields": list(slots.keys())})
        actions.append({"type":"email.reply", "template":"update_done"})
    elif intent == "規則詢問":
        actions.append({"type":"kb.search", "query":"policy"})
        actions.append({"type":"email.reply", "template":"policy_link"})
    else:
        actions.append({"type":"email.reply", "template":"generic"})
    return {"intent":intent, "slots":slots, "actions":actions}

def run_pipeline(email: Dict[str,Any], backend="rule") -> Dict[str,Any]:
    contract = load_contract()
    if backend=="rule":
        intent = classify_rule(email, contract)
    elif backend=="local":
        intent = classify_rule(email, contract)  # TODO: 接上本地模型
    else:
        intent = classify_rule(email, contract)  # TODO: 接上雲端模型
    slots = extract_slots_rule(email, intent)
    plan  = plan_rule(intent, slots)
    return {"intent":intent, "slots":slots, "plan":plan}

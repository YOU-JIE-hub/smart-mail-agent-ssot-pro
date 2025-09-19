from __future__ import annotations
import time, json, pathlib
from tools.orch.policy_engine import should_hitl

def plan(intent:str, slots:dict, email:dict, confidence:float)->dict:
    # 低信度 → HITL
    if should_hitl(intent, confidence):
        return {"action":"hitl_queue","ok":False,"route":{"channel":"hitl","dry_run":True},"required":[],"template":"hitl_v1","params":{"reason":"low_confidence","intent":intent,"confidence":confidence}}
    # 各意圖規劃
    if intent=="報價":
        qty  = int(slots.get("qty") or 1)
        price= int(slots.get("price") or 0)
        total= qty*price
        return {"action":"quote_reply","ok": (qty>0 and price>0),"route":{"channel":"email","dry_run":True},"required":["price","qty"],"template":"quote_email.md","params":{"item":"N/A","unit_price":price,"qty":qty,"subtotal":qty*price,"tax": int(qty*price*0.05),"total": int(total*1.05),"currency":"TWD","valid_until": time.strftime("%Y-%m-%d")}}
    if intent=="投訴":
        return {"action":"create_ticket","ok":True,"route":{"channel":"ticket","dry_run":True},"required":[],"template":"ticket_v1","params":{"severity":"P2","tags":["complaint"]}}
    if intent=="技術支援":
        return {"action":"create_ticket","ok":True,"route":{"channel":"ticket","dry_run":True},"required":[],"template":"ts_v1","params":{"severity":"P3","tags":["tech_support"]}}
    if intent=="規則詢問":
        return {"action":"policy_reply","ok":True,"route":{"channel":"email","dry_run":True},"required":[],"template":"reply_generic.md","params":{}}
    if intent=="資料異動":
        need= bool(slots.get("id"))
        return {"action":"update_record","ok":need,"route":{"channel":"crm","dry_run":True},"required":["id"],"template":"update_v1","params":{"id": slots.get("id")}}
    return {"action":"generic_reply","ok":True,"route":{"channel":"email","dry_run":True},"required":[],"template":"reply_generic.md","params":{}}

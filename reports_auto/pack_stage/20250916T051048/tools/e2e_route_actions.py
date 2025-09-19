from __future__ import annotations
import os, sys, json, time, re
from pathlib import Path

def _call_rule(email:dict):
    # 相容兩種 baseline：classify_rule(email, contract) / classify_rule(email)
    from tools import pipeline_baseline as base
    cls = getattr(base, "classify_rule", None) or getattr(base, "classify", None)
    if cls is None:
        raise ImportError("pipeline_baseline: classify_rule/classify not found")
    try:
        # 優先檢查是否需要 contract
        need_contract = "contract" in getattr(cls, "__code__", None).co_varnames if hasattr(cls, "__code__") else False
    except Exception:
        need_contract = False
    try:
        if need_contract:
            load = getattr(base, "load_contract", None)
            if callable(load):
                r = cls(email, load())
            else:
                r = cls(email)
        else:
            r = cls(email)
    except TypeError:
        # 再試一次帶 contract
        load = getattr(base, "load_contract", None)
        r = cls(email, load() if callable(load) else None)

    # 正規化輸出
    if isinstance(r, tuple):
        intent = r[0]; conf = float(r[2] if len(r)>2 else 1.0)
    elif isinstance(r, dict):
        intent = r.get("intent"); conf = float(r.get("confidence",1.0))
    else:
        intent = str(r); conf = 1.0
    return intent, conf

def _call_ml(email:dict):
    from tools.pipeline_ml import classify_ml as cls
    r = cls(email)
    if isinstance(r, tuple): intent, conf = r[0], float(r[2] if len(r)>2 else 1.0)
    elif isinstance(r, dict): intent, conf = r.get("intent"), float(r.get("confidence",1.0))
    else: intent, conf = str(r), 1.0
    return intent, conf

def _call_boosted(email:dict):
    from tools.pipeline_ml_boosted import classify_boosted as cls
    r = cls(email)
    if isinstance(r, tuple): intent, conf = r[0], float(r[2] if len(r)>2 else 1.0)
    elif isinstance(r, dict): intent, conf = r.get("intent"), float(r.get("confidence",1.0))
    else: intent, conf = str(r), 1.0
    return intent, conf

def _light_slots(email:dict) -> dict:
    text = (email.get("subject","") or "") + "\n" + (email.get("body","") or "")
    slots={}
    m=re.search(r"(單價|price)\D*(\d+(?:\.\d+)?)", text);  slots["price"]=float(m.group(2)) if m else None
    m=re.search(r"(數量|qty)\D*(\d+)", text);            slots["qty"]=int(m.group(2)) if m else None
    m=re.search(r"(品項|item)\D*([A-Za-z0-9\-_/]+)", text); slots["item"]=m.group(2) if m else "N/A"
    return slots

def main():
    backend = (sys.argv[1] if len(sys.argv)>1 else "rule").lower()
    samples = []
    fx = Path("fixtures/eval_set.jsonl")
    if fx.exists():
        for ln in fx.read_text(encoding="utf-8").splitlines():
            if ln.strip(): samples.append(json.loads(ln))
    else:
        samples=[{"intent":"報價","email":{"subject":"報價 單價:100 數量:2","body":""}},
                 {"intent":"技術支援","email":{"subject":"技術支援 ticket:TS-1234","body":""}}]

    from tools.orch.planner_bridge import plan_action
    from tools.actions.action_bus import ActionBus
    bus = ActionBus()
    for s in samples:
        email = s["email"]
        if backend=="rule":   intent, conf = _call_rule(email)
        elif backend=="ml":   intent, conf = _call_ml(email)
        else:                 intent, conf = _call_boosted(email)
        slots = _light_slots(email)
        plan = plan_action(intent, conf, email, slots)
        t0=time.time()
        res  = bus.execute(s.get("email_id") or time.strftime("%Y-%m-%dT%H%M%S"), intent, plan)
        res["latency_ms"] = (time.time()-t0)*1000
        print(json.dumps({"intent":intent,"conf":conf,"plan":plan,"result":res}, ensure_ascii=False))

if __name__=="__main__": main()

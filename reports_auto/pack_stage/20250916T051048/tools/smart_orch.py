from __future__ import annotations
import time, json
from tools.orch.planner_bridge import plan_action
from tools.actions.action_bus import ActionBus
from tools.pipeline_ml_boosted import classify_ml_boosted as classify_boosted
from tools.pipeline_ml import classify_ml
from tools.pipeline_baseline import classify as classify_rule
from tools.kie.slots import extract_slots

def _compose(email:dict)->str:
    return (str(email.get("subject",""))+"\n"+str(email.get("body",""))).strip()

def _classify(email:dict, backend:str)->tuple[str,float]:
    if backend=="rule":
        r=classify_rule(email); return (r[0], r[1]) if isinstance(r,tuple) else (r,1.0)
    if backend=="ml":
        o=classify_ml(email); return (o["intent"], float(o.get("confidence",0.0)))
    o=classify_boosted(email); return (o["intent"], float(o.get("confidence",0.88)))

def _enrich_plan(intent:str, plan:dict, email:dict)->dict:
    need_price_qty = (intent=="報價")
    need_ticket    = (intent=="技術支援")
    if not (need_price_qty or need_ticket): return plan
    slots = extract_slots(email)
    new = dict(plan); p = dict(new.get("params",{}))
    upgraded=False
    if need_price_qty and slots.get("price") and slots.get("qty"):
        if new.get("action")=="hitl_queue":
            new["action"]="quote_reply"; new["ok"]=True; upgraded=True
        p.update({"unit_price":float(slots["price"]), "qty":int(slots["qty"])})
    if need_ticket and slots.get("ticket"):
        if new.get("action")=="hitl_queue":
            new["action"]="create_ticket"; new["ok"]=True; upgraded=True
        p.update({"severity":"P3","tags":["tech_support"],"summary":_compose(email)})
    if upgraded or p!=new.get("params"):
        new["params"]=p
    return new

def run(email:dict, backend:str="boosted", dry:bool=True)->dict:
    intent, conf = _classify(email, backend)
    plan = plan_action(intent, conf, email, slots={})
    plan = _enrich_plan(intent, plan, email)
    res  = ActionBus().execute(f"mail-{int(time.time()*1000)}", intent, plan, dry_run=dry)
    return {"intent":intent, "conf":conf, "plan":plan, "result":res}

if __name__=="__main__":
    import sys
    email=json.loads(sys.stdin.read())
    print(json.dumps(run(email), ensure_ascii=False))

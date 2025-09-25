import re, yaml, pathlib
CFG=pathlib.Path("scripts/policy/rules.yaml")
RULES=yaml.safe_load(CFG.read_text(encoding="utf-8")) if CFG.exists() else {"rules":[]}
def explain(text:str):
    hits=[]
    for r in RULES.get("rules",[]):
        if any(re.search(re.escape(k), text) for k in r.get("any",[])):
            hits.append({"rule_id":r["id"],"intent":r["intent"],"matched":True})
    intent = hits[0]["intent"] if hits else "other"
    return {"intent_hint": intent, "reasons": hits}

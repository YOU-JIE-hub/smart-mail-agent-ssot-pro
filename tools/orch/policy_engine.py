from __future__ import annotations
import json, pathlib, os
INTENT_THR = pathlib.Path("reports_auto/intent/reports_auto/intent_thresholds.json")
def load_thresholds():
    if INTENT_THR.exists():
        return json.loads(INTENT_THR.read_text(encoding="utf-8"))
    # fallback
    return {"p1":0.52, "margin":0.15, "lock": True}

def should_hitl(intent:str, confidence:float)->bool:
    cfg=load_thresholds()
    p1=cfg.get("p1",0.5)
    return confidence < p1

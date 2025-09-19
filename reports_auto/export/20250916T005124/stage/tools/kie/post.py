
from __future__ import annotations
from typing import List, Dict

def _touch_or_overlap(a:dict,b:dict, pad:int=1)->bool:
    return not (a["end"]+pad < b["start"] or b["end"]+pad < a["start"])

def _merge(a:dict,b:dict)->dict:
    return {"start": min(a["start"],b["start"]), "end": max(a["end"],b["end"]), "label": a["label"]}

def postprocess_spans(text:str, spans:List[Dict])->List[Dict]:
    if not spans: return spans
    spans = sorted(spans, key=lambda s:(s["label"], s["start"], s["end"]))
    out=[]
    for s in spans:
        if out and out[-1]["label"]==s["label"] and _touch_or_overlap(out[-1], s, pad=1):
            out[-1] = _merge(out[-1], s)
        else:
            out.append(s)
    # 數值正規化交由消費端（此處先保留原 index，避免破壞對齊）
    return out

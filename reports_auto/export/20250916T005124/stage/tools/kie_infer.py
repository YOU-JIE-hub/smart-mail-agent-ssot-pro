from __future__ import annotations
import re, time
from typing import TypedDict

class KIEResult(TypedDict, total=False):
    slots: dict
    confidence: float
    spans: list

NUM=re.compile(r"(?:單價|單價:|price[:：]?)\D*(\d+(?:\.\d+)?)", re.I)
QTY=re.compile(r"(?:數量|qty|quantity)[:：]?\D*(\d+)", re.I)
OID=re.compile(r"(?:order|ord|單號)[:：]?\s*([A-Z]{2,4}[-_]?\d+)", re.I)
DATE=re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})")

def extract_slots(email:dict)->KIEResult:
    text=" ".join([email.get("subject",""), email.get("body","")])
    slots={}
    m=NUM.search(text);  slots["price"]=float(m.group(1)) if m else None
    m=QTY.search(text);  slots["qty"]=int(m.group(1)) if m else None
    m=OID.search(text);  slots["id"]=m.group(1) if m else None
    m=DATE.search(text); slots["date"]=m.group(1) if m else None
    conf=0.9 if all(slots.get(k) for k in ("price","qty")) else 0.5
    return {"slots":slots,"confidence":conf,"spans":[]}


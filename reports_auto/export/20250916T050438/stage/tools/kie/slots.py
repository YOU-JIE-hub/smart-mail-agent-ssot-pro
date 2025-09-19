from __future__ import annotations
import re
from typing import Dict, Any
from .hf_kie import decode

def _compose(email:dict)->str:
    return (str(email.get("subject",""))+"\n"+str(email.get("body",""))).strip()

def _fallback_regex(text:str)->Dict[str,Any]:
    price=None; qty=None; ticket=None
    m=re.search(r"(?:NT\$|US\$|\$|＄)\s?([0-9][0-9,]*(?:\.[0-9]+)?)", text, re.I)
    if m: price=float(m.group(1).replace(",",""))
    m=re.search(r"\b(?:qty|數量)[\s:=\-]*([0-9]+)\b", text, re.I)
    if m: qty=int(m.group(1))
    m=re.search(r"\b(?:ticket|ts|單號)[:\- ]?([A-Z]{2,5}-?[0-9]{3,8})\b", text, re.I)
    if m: ticket=m.group(1)
    return {"price":price,"qty":qty,"ticket":ticket}

def extract_slots(email:dict)->Dict[str,Any]:
    text=_compose(email)
    try:
        spans=decode(text)
    except Exception:
        return _fallback_regex(text)
    price=None; qty=None; ticket=None
    for s in spans:
        lab=s.get("label","").lower()
        seg=text[s["start"]:s["end"]]
        if lab=="amount":
            m=re.search(r"([0-9][0-9,]*(?:\.[0-9]+)?)", seg)
            if m: price=float(m.group(1).replace(",",""))
        elif lab in ("qty","quantity"):
            m=re.search(r"([0-9]{1,5})", seg)
            if m: qty=int(m.group(1))
        elif lab in ("ticket","case","id"):
            ticket=seg.strip()
    if price is None or qty is None or ticket is None:
        fb=_fallback_regex(text)
        price=price if price is not None else fb["price"]
        qty=qty if qty is not None else fb["qty"]
        ticket=ticket if ticket is not None else fb["ticket"]
    return {"price":price,"qty":qty,"ticket":ticket}

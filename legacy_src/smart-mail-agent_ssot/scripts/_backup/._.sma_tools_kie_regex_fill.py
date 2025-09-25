#!/usr/bin/env python3
import argparse, json, re, unicodedata
from pathlib import Path
def norm(s):
    if s is None: return ""
    s=unicodedata.normalize("NFKC",str(s)).replace("\u3000"," ")
    return re.sub(r"\s+"," ",s).strip()
def load_jsonl(p):
    L=[]; 
    with Path(p).open(encoding="utf-8",errors="ignore") as f:
        for ln in f:
            if ln.strip(): L.append(json.loads(ln))
    return L
def text_of(o):
    parts=[]
    for k in ("body","text","content","plain","raw_text","snippet","summary","description","body_norm","text_norm"):
        v=o.get(k); 
        if isinstance(v,str): parts.append(v)
    for kk in ("src","email","payload","data"):
        v=o.get(kk)
        if isinstance(v,dict):
            for k in ("body","text","content","plain","raw_text","snippet","summary","description"):
                vv=v.get(k)
                if isinstance(vv,str): parts.append(vv)
    return norm("\n".join(parts))[:4000]
AMOUNT=re.compile(r"(?:\$|USD|NT\$|NTD|TWD|NT)?\s?([1-9]\d{0,2}(?:[,\d]{0,3})*(?:\.\d{1,2})?)")
DATE=re.compile(r"(\d{4}[-/年\.]\d{1,2}[-/月\.]\d{1,2}|\d{1,2}[:/]\d{1,2}[:/]\d{2,4})")
SLA =re.compile(r"\b(SLA|service level|回應時限|工單時限)\b",re.I)
ENV =re.compile(r"\b(prod|production|uat|staging|stage|dev|testing)\b",re.I)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--src",required=True)
    ap.add_argument("--pred_in",required=True)
    ap.add_argument("--pred_out",required=True)
    a=ap.parse_args()
    src=load_jsonl(a.src); src_map={str(o.get("id","")):o for o in src}
    pred=load_jsonl(a.pred_in)
    before_empty=after_empty=filled=0
    for o in pred:
        spans=((o.get("kie") or {}).get("spans") or [])
        if not spans: before_empty+=1
        if spans:
            o["kie"]={"spans":spans}
            continue
        s=src_map.get(str(o.get("id","")),{})
        t=text_of(s) or text_of(o)
        out=[]
        m=AMOUNT.search(t)
        if m: out.append({"label":"amount","text":m.group(1),"source":"regex"})
        m=DATE.search(t)
        if m: out.append({"label":"date_time","text":m.group(1),"source":"regex"})
        if SLA.search(t): out.append({"label":"sla","text":"SLA","source":"regex"})
        m=ENV.search(t)
        if m: out.append({"label":"env","text":m.group(1).lower(),"source":"regex"})
        o["kie"]={"spans":out}
        if out: filled+=1
    after_empty=sum(1 for o in pred if not ((o.get("kie") or {}).get("spans") or []))
    with Path(a.pred_out).open("w",encoding="utf-8") as g:
        for o in pred: g.write(json.dumps(o,ensure_ascii=False)+"\n")
    print(f"[REGEX-FILL] before_empty={before_empty} filled={filled} after_empty={after_empty} -> {a.pred_out}")
if __name__=="__main__": main()

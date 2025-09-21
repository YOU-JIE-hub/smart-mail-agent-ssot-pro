#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path

def norm_amount(s):
    t = s.replace("，",",").replace("．",".").replace("＄","$").replace(" ", "")
    m = re.search(r"(NT\$|USD|\$)\s?([0-9][0-9,]*)(?:\.(\d+))?", t, re.I)
    if not m: return None
    cur = m.group(1).upper().replace("＄","$")
    val = float(m.group(2).replace(",","") + ("."+m.group(3) if m.group(3) else ""))
    return cur, val
def norm_date(s):
    t = s.replace("．",".").replace("年","-").replace("月","-").replace("日","")
    t = t.replace(".", "-").replace("/", "-")
    m = re.search(r"([12]\d{3})-(\d{1,2})-(\d{1,2})", t)
    if m: return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{1,2})-(\d{1,2})$", t)
    if m: return f"--{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return None
ENV_MAP = {"production":"prod","prd":"prod","staging":"staging","stage":"staging","stg":"staging","uat":"uat","test":"test","dev":"dev","prod":"prod"}
def norm_env(s):
    return ENV_MAP.get(s.lower(), s.lower())

def load_jsonl(p):
    rows=[]; 
    with open(p,encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln); rows.append(o)
    return rows

def text_to_fields(o):
    # 將 spans 切片回文字，做正規化
    t=o["text"]; f={"amount":None,"date_time":None,"env":None,"sla":None}
    for sp in o.get("spans",[]):
        seg=t[sp["start"]:sp["end"]]; lab=sp["label"]
        if lab=="amount": f["amount"]=norm_amount(seg)
        elif lab=="date_time": f["date_time"]=norm_date(seg)
        elif lab=="env": f["env"]=norm_env(seg)
        elif lab=="sla": f["sla"]=seg.upper()
    return f

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pred", default="reports_auto/kie_pred.jsonl")
    ap.add_argument("--gold", default="data/kie/test.jsonl")
    ap.add_argument("--out",  default="reports_auto/kie_field_recall.txt")
    a=ap.parse_args()
    P=load_jsonl(a.pred); G=load_jsonl(a.gold)
    # 以 text 對齊
    from collections import defaultdict, deque
    gm=defaultdict(deque)
    for g in G: gm[g["text"]].append(g)
    tot={"amount":0,"date_time":0,"env":0,"sla":0}; hit=tot.copy()
    for p in P:
        if not gm[p["text"]]: continue
        g=gm[p["text"]].popleft()
        pf=text_to_fields(p); gf=text_to_fields(g)
        for k in tot:
            if gf[k] is not None: tot[k]+=1
            if gf[k] is not None and pf[k]==gf[k]: hit[k]+=1
    lines=["# field-level recall / value-equivalence",
           *(f"{k}_recall={ (hit[k]/tot[k]):.4f}" if tot[k] else f"{k}_recall=NA" for k in ("amount","date_time","env","sla")),
           f"support: "+", ".join(f"{k}={tot[k]}" for k in tot)]
    Path(a.out).write_text("\n".join(lines), encoding="utf-8")
    print("[FIELDS] ->", a.out); print("\n".join(lines))
if __name__=="__main__": main()

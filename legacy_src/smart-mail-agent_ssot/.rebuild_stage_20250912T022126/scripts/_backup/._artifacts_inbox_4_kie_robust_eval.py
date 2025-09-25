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
    t=s.replace("．",".").replace("年","-").replace("月","-").replace("日","")
    t=t.replace("/", "-").replace(".", "-")
    import re
    m=re.search(r"([12]\d{3})-(\d{1,2})-(\d{1,2})",t)
    if m: return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
    m=re.search(r"(\d{1,2})-(\d{1,2})$",t)
    if m: return f"--{int(m[1]):02d}-{int(m[2]):02d}"
    return None

def norm_env(s):
    mp={"production":"prod","prd":"prod","staging":"staging","stage":"staging","stg":"staging",
        "uat":"uat","test":"test","dev":"dev","prod":"prod"}
    return mp.get(s.lower(), s.lower())

def load_spans(p): return [json.loads(l) for l in Path(p).open(encoding="utf-8")]
def fields(o):
    t=o["text"]; f={"amount":None,"date_time":None,"env":None}
    for s in o.get("spans",[]):
        seg=t[s["start"]:s["end"]]
        if s["label"]=="amount": f["amount"]=norm_amount(seg)
        elif s["label"]=="date_time": f["date_time"]=norm_date(seg)
        elif s["label"]=="env": f["env"]=norm_env(seg)
    return f

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pred_base", default="reports_auto/kie_pred.jsonl")
    ap.add_argument("--pred_aug",  default="reports_auto/kie_pred_perturb.jsonl")
    ap.add_argument("--out", default="reports_auto/kie_robust.txt")
    a=ap.parse_args()
    B=load_spans(a.pred_base); A=load_spans(a.pred_aug)
    n=min(len(B), len(A))
    ok={"amount":0,"date_time":0,"env":0}; tot={"amount":0,"date_time":0,"env":0}
    for i in range(n):
        fb=fields(B[i]); fa=fields(A[i])
        for k in ok:
            if fb[k] is not None or fa[k] is not None: tot[k]+=1
            if fb[k]==fa[k] and fb[k] is not None: ok[k]+=1
    lines=[f"{k}_stability={(ok[k]/tot[k]):.4f}" if tot[k] else f"{k}_stability=NA" for k in ok]
    Path(a.out).write_text("\n".join(lines)+f"\nsupport={tot}", encoding="utf-8")
    print("[ROBUST] ->", a.out); print("\n".join(lines))
if __name__=="__main__": main()

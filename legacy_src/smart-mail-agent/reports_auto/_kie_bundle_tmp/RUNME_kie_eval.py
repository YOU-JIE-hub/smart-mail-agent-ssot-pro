#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json
from pathlib import Path

def read_gold(p: Path):
    G=[]
    with open(p,"r",encoding="utf-8") as f:
        for i,ln in enumerate(f,1):
            if not ln.strip(): continue
            o=json.loads(ln)
            text=o.get("text") or ((o.get("subject","")+"\n"+o.get("body","")).strip())
            gold=o.get("spans") or []
            rows=[(s.get("label"), int(s.get("start",0)), int(s.get("end",0))) for s in gold]
            G.append((o.get("id",f"ex-{i:04d}"), text, rows))
    return G

def read_pred_tsv(p: Path):
    P=[]
    with open(p,"r",encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        idx = {k:i for i,k in enumerate(header)}
        for ln in f:
            if not ln.strip(): continue
            cols=ln.rstrip("\n").split("\t")
            P.append((cols[idx["id"]], cols[idx["label"]], int(cols[idx["start"]]), int(cols[idx["end"]])))
    by={}
    for _id,lab,st,ed in P:
        by.setdefault(_id, []).append((lab,st,ed))
    return by

def strict_prf(gold_jsonl: Path, pred_tsv: Path):
    G=read_gold(gold_jsonl); P=read_pred_tsv(pred_tsv)
    tp=fp=fn=0
    for _id, _text, gspans in G:
        pspans=set(P.get(_id, [])); gspans=set(gspans)
        tp += len(gspans & pspans)
        fp += len(pspans - gspans)
        fn += len(gspans - pspans)
    Pp = (tp/(tp+fp)) if (tp+fp)>0 else 0.0
    Rr = (tp/(tp+fn)) if (tp+fn)>0 else 0.0
    F1 = (2*Pp*Rr/(Pp+Rr)) if (Pp+Rr)>0 else 0.0
    return Pp,Rr,F1,tp,fp,fn

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--gold", required=True, help="gold jsonl with text+spans")
    ap.add_argument("--pred", required=True, help="pred TSV from RUNME_kie_demo.py")
    a=ap.parse_args()
    P,R,F1,tp,fp,fn = strict_prf(Path(a.gold), Path(a.pred))
    print(f"strict_span_P={P:.4f}")
    print(f"strict_span_R={R:.4f}")
    print(f"strict_span_F1={F1:.4f}")
    print(f"(tp={tp}, fp={fp}, fn={fn})")

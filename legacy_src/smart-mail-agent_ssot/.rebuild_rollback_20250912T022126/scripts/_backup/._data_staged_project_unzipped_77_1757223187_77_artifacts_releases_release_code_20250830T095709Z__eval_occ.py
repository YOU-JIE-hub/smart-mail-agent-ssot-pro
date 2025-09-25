#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, sys
from collections import defaultdict, deque
pred_path, gold_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
def load_occ_rows(p):
    occ=defaultdict(int); rows=[]
    with open(p,encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln); t=o["text"]; k=(t,occ[t]); occ[t]+=1
            S=set((s["start"],s["end"],s["label"]) for s in o.get("spans",[]))
            rows.append((k,S))
    return rows
P=load_occ_rows(pred_path); G=load_occ_rows(gold_path)
gmap=defaultdict(deque)
for k,S in G: gmap[k].append(S)
tp=fp=fn=0; aligned=0
for k,Ps in P:
    if gmap[k]:
        Gs=gmap[k].popleft(); aligned+=1
        tp+=len(Ps & Gs); fp+=len(Ps - Gs); fn+=len(Gs - Ps)
prec = tp/(tp+fp) if tp+fp else 0.0
rec  = tp/(tp+fn) if tp+fn else 0.0
f1   = 2*prec*rec/(prec+rec) if prec+rec else 0.0
with open(out_path,"w",encoding="utf-8") as fo:
    fo.write("aligned_rows=%d\nstrict_span_P=%.4f\nstrict_span_R=%.4f\nstrict_span_F1=%.4f\n" % (aligned,prec,rec,f1))
print("[EVAL] ->", out_path)

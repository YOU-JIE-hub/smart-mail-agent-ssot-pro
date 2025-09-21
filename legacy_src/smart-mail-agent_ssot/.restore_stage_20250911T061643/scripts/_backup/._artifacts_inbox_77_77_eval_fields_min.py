#!/usr/bin/env python3
import sys,json,collections
pred, gold, outp = sys.argv[1], sys.argv[2], sys.argv[3]
def load(p):
  m={}
  for ln in open(p,encoding='utf-8'):
    o=json.loads(ln); m[o["text"]]=[(s["start"],s["end"],s["label"]) for s in o.get("spans",[])]
  return m
P=load(pred); G=load(gold)
labs=["amount","date_time","env","sla"]; stat=collections.defaultdict(lambda:collections.Counter())
for t,gs in G.items():
  ps=set(P.get(t,[])); gs=set(gs)
  for l in labs:
    P_l=set([x for x in ps if x[2]==l]); G_l=set([x for x in gs if x[2]==l])
    tp=len(P_l & G_l); fp=len(P_l - G_l); fn=len(G_l - P_l)
    stat[l]["tp"]+=tp; stat[l]["fp"]+=fp; stat[l]["fn"]+=fn
with open(outp,"w",encoding="utf-8") as fo:
  for l in labs:
    tp,fp,fn=stat[l]["tp"],stat[l]["fp"],stat[l]["fn"]
    P=tp/(tp+fp) if tp+fp else 0.0; R=tp/(tp+fn) if tp+fn else 0.0; F=2*P*R/(P+R) if P+R else 0.0
    fo.write(f"{l}_P={P:.4f} {l}_R={R:.4f} {l}_F1={F:.4f}  (tp={tp}, fp={fp}, fn={fn})\n")
print("[FIELDS] ->", outp)

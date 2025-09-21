#!/usr/bin/env python3
import json, sys, random
R=random.Random(42)
def load(p):
    m={}
    with open(p,encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln); m[o["text"]]=set((s["start"],s["end"],s["label"]) for s in o.get("spans",[]))
    return m
pred_rule, pred_model, gold_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
A=load(pred_rule); B=load(pred_model); 
G=load(gold_path)
keys=sorted(set(G)&set(A)&set(B))
def f1(P,G):
    tp=len(P&G); fp=len(P-G); fn=len(G-P)
    Pp=tp/(tp+fp) if tp+fp else 0.0; Rp=tp/(tp+fn) if tp+fn else 0.0; 
    return 2*Pp*Rp/(Pp+Rp) if Pp+Rp else 0.0
FA=f1(set().union(*[A[k] for k in keys]) if keys else set(), set().union(*[G[k] for k in keys]) if keys else set())
FB=f1(set().union(*[B[k] for k in keys]) if keys else set(), set().union(*[G[k] for k in keys]) if keys else set())
diff=FB-FA
better=0
for _ in range(2000):
    SA=[]; SB=[]
    for k in keys:
        if R.random()<0.5: SA.append(A[k]); SB.append(B[k])
        else: SA.append(B[k]); SB.append(A[k])
    FA2=f1(set().union(*SA) if SA else set(), set().union(*[G[k] for k in keys]) if keys else set())
    FB2=f1(set().union(*SB) if SB else set(), set().union(*[G[k] for k in keys]) if keys else set())
    if (FB2-FA2)>=diff: better+=1
p=(better+1)/(2000+1)
open(out_path,"w",encoding="utf-8").write(f"A(rule)_F1={FA:.4f}\nB(model)_F1={FB:.4f}\nDelta={diff:.4f}\np_perm={p:.4f}\nN={len(keys)}\n")
print("[CMP] ->", out_path)

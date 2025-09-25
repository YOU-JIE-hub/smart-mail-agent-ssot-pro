#!/usr/bin/env python3
import sys,json,random
R=random.Random(42)
pred, gold, outp = sys.argv[1], sys.argv[2], sys.argv[3]
def load(p):
  m={}
  for ln in open(p,encoding='utf-8'):
    o=json.loads(ln); m[o["text"]]=set((s["start"],s["end"],s["label"]) for s in o.get("spans",[]))
  return m
P=load(pred); G=load(gold)
pairs=[(t,P[t],G[t]) for t in P.keys() & G.keys()]
def prf(prs):
  tp=fp=fn=0
  for _,ps,gs in prs: tp+=len(ps&gs); fp+=len(ps-gs); fn+=len(gs-ps)
  P=tp/(tp+fp) if tp+fp else 0.0; R=tp/(tp+fn) if tp+fn else 0.0; F=2*P*R/(P+R) if P+R else 0.0
  return F
F=prf(pairs)
Fs=[]
for _ in range(1000):
  if not pairs: Fs.append(0.0); continue
  samp=[pairs[R.randrange(len(pairs))] for __ in range(len(pairs))]
  Fs.append(prf(samp))
Fs.sort(); lo=Fs[int(0.025*len(Fs))]; hi=Fs[int(0.975*len(Fs))-1]
open(outp,"w",encoding="utf-8").write(f"strict_span_F1={F:.4f}\nF1_95CI=[{lo:.4f},{hi:.4f}]\npairs={len(pairs)}\n")
print("[CI] ->", outp)

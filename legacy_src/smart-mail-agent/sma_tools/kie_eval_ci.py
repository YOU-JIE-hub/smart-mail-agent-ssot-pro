#!/usr/bin/env python3
import json, sys, random
R=random.Random(42)
pred_path, gold_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
def load(p):
    rows=[]
    with open(p,encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln); rows.append((o["text"], {(s["start"],s["end"],s["label"]) for s in o.get("spans",[]) }))
    return rows
P = load(pred_path); G = dict(load(gold_path))
pairs = [(t, ps, G.get(t,set())) for t,ps in P if t in G]
def prf(pairs):
    tp=fp=fn=0
    for _,ps,gs in pairs: tp+=len(ps&gs); fp+=len(ps-gs); fn+=len(gs-ps)
    P=tp/(tp+fp) if tp+fp else 0.0; R=tp/(tp+fn) if tp+fn else 0.0; F=2*P*R/(P+R) if P+R else 0.0
    return P,R,F
_,_,F = prf(pairs)
Fs=[]
for _ in range(2000):
    samp=[pairs[R.randrange(len(pairs))] for __ in range(len(pairs))] or []
    Fs.append(prf(samp)[2] if samp else 0.0)
Fs.sort(); lo=Fs[int(0.025*len(Fs))] if Fs else 0.0; hi=Fs[int(0.975*len(Fs))-1] if Fs else 0.0
open(out_path,"w",encoding="utf-8").write(f"strict_span_F1={F:.4f}\nF1_95CI=[{lo:.4f},{hi:.4f}]\npairs={len(pairs)}\n")
print("[CI] ->", out_path)

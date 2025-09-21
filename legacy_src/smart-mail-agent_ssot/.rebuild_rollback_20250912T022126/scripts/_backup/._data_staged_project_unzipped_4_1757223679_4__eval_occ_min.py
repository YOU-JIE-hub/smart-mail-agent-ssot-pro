#!/usr/bin/env python3
import sys,json,collections
pred, gold, outp = sys.argv[1], sys.argv[2], sys.argv[3]
def load_occ(p):
  occ=collections.defaultdict(int); rows=[]
  for ln in open(p,encoding='utf-8'):
    o=json.loads(ln); t=o["text"]; k=(t,occ[t]); occ[t]+=1
    rows.append((k, set((s["start"],s["end"],s["label"]) for s in o.get("spans",[]))))
  return rows
P=load_occ(pred); G=load_occ(gold)
# align by (text,occ)
gmap={}
for k,s in G: gmap.setdefault(k,[]).append(s)
tp=fp=fn=0; aligned=0
for k,ps in P:
  if k in gmap and gmap[k]:
    gs=gmap[k].pop(0); aligned+=1
    tp+=len(ps&gs); fp+=len(ps-gs); fn+=len(gs-ps)
P_=tp/(tp+fp) if tp+fp else 0.0; R_=tp/(tp+fn) if tp+fn else 0.0; F= 2*P_*R_/(P_+R_) if P_+R_ else 0.0
open(outp,"w",encoding="utf-8").write(f"aligned_rows={aligned}\nstrict_span_P={P_:.4f}\nstrict_span_R={R_:.4f}\nstrict_span_F1={F:.4f}\n")
print("[EVAL] ->", outp)

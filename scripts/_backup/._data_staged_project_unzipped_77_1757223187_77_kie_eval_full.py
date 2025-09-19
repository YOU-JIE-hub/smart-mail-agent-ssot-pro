#!/usr/bin/env python3
import sys, json
from collections import defaultdict, deque
def load_occ_rows(p):
    occ=defaultdict(int); rows=[]
    with open(p,encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln); t=o["text"]; k=(t,occ[t]); occ[t]+=1
            S={(s["start"],s["end"],s["label"]) for s in o.get("spans",[])}
            rows.append((k,S))
    return rows
def prf(tp,fp,fn):
    P=len(tp)/(len(tp)+len(fp)) if (len(tp)+len(fp)) else 0.0
    R=len(tp)/(len(tp)+len(fn)) if (len(tp)+len(fn)) else 0.0
    F=2*P*R/(P+R) if (P+R) else 0.0
    return P,R,F
def main():
    pred_path=sys.argv[1]; gold_path=sys.argv[2]; out_path=sys.argv[3]
    P=load_occ_rows(pred_path); G=load_occ_rows(gold_path)
    gmap=defaultdict(deque)
    for k,S in G: gmap[k[0]].append(S)
    tp=set(); fp=set(); fn=set()
    aligned=0
    for k,S in P:
        t,occ=k; ifq = gmap[t]
        if ifq:
            Gs=ifq.popleft(); aligned+=1
            tp|= (S & Gs); fp|= (S - Gs); fn|= (Gs - S)
        else:
            # pred 多出的文本出現
            for s in S: fp.add(s)
    Pm,Rm,Fm=prf(tp,fp,fn)
    with open(out_path,"w",encoding="utf-8") as fo:
        fo.write(f"pred_rows={len(P)}\n")
        fo.write(f"gold_rows={len(G)}\n")
        fo.write(f"aligned_rows={aligned}\n")
        fo.write(f"miss_from_pred={len(fn)}  # gold多出、pred缺少的出現次數\n")
        fo.write(f"miss_from_gold={len(fp)}  # pred多出、gold缺少的出現次數\n")
        fo.write(f"strict_span_P={Pm:.4f}\nstrict_span_R={Rm:.4f}\nstrict_span_F1={Fm:.4f}\n")
    print("[EVAL] ->", out_path)
if __name__=="__main__": main()

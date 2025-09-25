#!/usr/bin/env python3
import argparse, json, csv, collections, statistics as st
from pathlib import Path
def load_jsonl(p):
    L=[]; 
    with Path(p).open(encoding="utf-8",errors="ignore") as f:
        for ln in f:
            if ln.strip(): L.append(json.loads(ln))
    return L
def load_map_csv(p):
    M={}; 
    with Path(p).open(encoding="utf-8",errors="ignore") as f:
        r=csv.DictReader(f)
        for row in r: M[row["gold_id"]]=row["pred_id"]
    return M
def f1(p,r): return 0.0 if (p+r)==0 else 2*p*r/(p+r)
def eval_intent(gold,pred,map_path,out):
    G=load_jsonl(gold); P=load_jsonl(pred); M=load_map_csv(map_path)
    P_int={str(o.get("id","")): (o.get("intent") or {}).get("tuned") or (o.get("intent") or {}).get("label") or (o.get("intent") or {}).get("pred") or "other" for o in P}
    y_true=[]; y_pred=[]
    for g in G:
        gid=str(g.get("id") or g.get("gold_id") or "")
        if gid in M:
            y_true.append(str(g.get("label"))); y_pred.append(str(P_int.get(M[gid],"other")))
    labels=sorted(set(y_true)|set(y_pred)); per=collections.OrderedDict()
    for lb in labels:
        tp=sum(1 for t,p in zip(y_true,y_pred) if t==lb and p==lb)
        fp=sum(1 for t,p in zip(y_true,y_pred) if t!=lb and p==lb)
        fn=sum(1 for t,p in zip(y_true,y_pred) if t==lb and p!=lb)
        prec=0.0 if (tp+fp)==0 else tp/(tp+fp); rec=0.0 if (tp+fn)==0 else tp/(tp+fn)
        per[lb]=(len([1 for t in y_true if t==lb]),prec,rec,f1(prec,rec))
    acc = 0.0 if not y_true else sum(1 for t,p in zip(y_true,y_pred) if t==p)/len(y_true)
    macro = st.mean([v[3] for v in per.values()]) if per else 0.0
    micro = acc; weighted = (sum(v[0]*v[3] for v in per.values())/sum(v[0] for v in per.values())) if per else 0.0
    Path(out).write_text(
        "TASK=intent\n"
        f"GOLD={len(G)} MATCHED={len(y_true)} COVERAGE={(len(y_true)/len(G)) if G else 0:.4f}\n"
        f"ACCURACY={acc:.4f}\n"
        f"F1_macro={macro:.4f} F1_micro={micro:.4f} F1_weighted={weighted:.4f}\n"
        "PER_LABEL (label, support, precision, recall, f1)\n" +
        "\n".join([f"{k}\t{v[0]}\t{v[1]:.4f}\t{v[2]:.4f}\t{v[3]:.4f}" for k,v in per.items()]),
        encoding="utf-8")
    print("[WRITE]",out)
def eval_spam(gold,pred,map_path,out,th=0.5):
    G=load_jsonl(gold); P=load_jsonl(pred); M=load_map_csv(map_path)
    G_map={str(o.get("id")): int(o.get("label")) for o in G if "label" in o}
    P_s={}
    for o in P:
        pid=str(o.get("id","")); sp=o.get("spam") or {}
        try: P_s[pid]=float(sp.get("score_text",0.0))
        except: P_s[pid]=0.0
    y_true=[]; y_score=[]
    for gid,pid in M.items():
        if gid in G_map and pid in P_s: y_true.append(G_map[gid]); y_score.append(P_s[pid])
    y_pred=[1 if s>=th else 0 for s in y_score]
    tp=sum(1 for t,p in zip(y_true,y_pred) if t==1 and p==1)
    fp=sum(1 for t,p in zip(y_true,y_pred) if t==0 and p==1)
    fn=sum(1 for t,p in zip(y_true,y_pred) if t==1 and p==0)
    tn=sum(1 for t,p in zip(y_true,y_pred) if t==0 and p==0)
    prec = 0.0 if (tp+fp)==0 else tp/(tp+fp); rec=0.0 if (tp+fn)==0 else tp/(tp+fn)
    acc  = (tp+tn)/len(y_true) if y_true else 0.0
    Path(out).write_text(
        f"TASK=spam threshold={th}\n"
        f"GOLD={len(G)} MATCHED={len(y_true)} COVERAGE={(len(y_true)/len(G)) if G else 0:.4f}\n"
        f"ACCURACY={acc:.4f} AUC=0.5\n"
        f"F1_macro={f1(prec,rec):.4f} F1_micro={acc:.4f} F1_weighted={f1(prec,rec):.4f}\n"
        "PER_LABEL (label, support, precision, recall, f1, TP, FP, FN)\n"
        f"0\t{len([1 for t in y_true if t==0])}\t{(tn/(tn+fn)) if (tn+fn)>0 else 0:.4f}\t{(tn/(tn+fp)) if (tn+fp)>0 else 0:.4f}\t0.0000\t{tn}\t{fp}\t{fn}\n"
        f"1\t{len([1 for t in y_true if t==1])}\t{prec:.4f}\t{rec:.4f}\t{f1(prec,rec):.4f}\t{tp}\t{fp}\t{fn}\n",
        encoding="utf-8")
    print("[WRITE]",out)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--task",required=True,choices=["intent","spam"])
    ap.add_argument("--gold",required=True); ap.add_argument("--pred",required=True)
    ap.add_argument("--map",required=True); ap.add_argument("--out",required=True)
    ap.add_argument("--spam_threshold",type=float,default=0.5)
    a=ap.parse_args()
    if a.task=="intent": eval_intent(a.gold,a.pred,a.map,a.out)
    else: eval_spam(a.gold,a.pred,a.map,a.out,a.spam_threshold)
if __name__=="__main__": main()

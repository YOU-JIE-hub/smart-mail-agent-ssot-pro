#!/usr/bin/env python3
import argparse, json, csv, math
from pathlib import Path
def load_jsonl(p):
    L=[]; 
    with Path(p).open(encoding="utf-8",errors="ignore") as f:
        for ln in f:
            if ln.strip(): L.append(json.loads(ln))
    return L
def load_map(p):
    M={}; 
    with Path(p).open(encoding="utf-8",errors="ignore") as f:
        r=csv.DictReader(f)
        for row in r: M[row["gold_id"]]=row["pred_id"]
    return M
def sigmoid(x):
    try:
        v=float(x)
        if 0.0<=v<=1.0: return v
        return 1/(1+math.exp(-v))
    except: return None
def fbeta(p,r,b=2.0):
    if p==0 and r==0: return 0.0
    b2=b*b; return (1+b2)*p*r/(b2*p+r) if (b2*p+r)>0 else 0.0
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--gold",required=True); ap.add_argument("--pred",required=True)
    ap.add_argument("--map",required=True); ap.add_argument("--out",required=True)
    ap.add_argument("--beta",type=float,default=2.0)
    a=ap.parse_args()
    G=load_jsonl(a.gold); P=load_jsonl(a.pred); M=load_map(a.map)
    G_map={str(o.get("id")): int(o.get("label")) for o in G if "label" in o}
    cand_names=["score_text","pred_ens","pred_text"]
    rows=[]
    for name in cand_names:
        S={}
        for o in P:
            pid=str(o.get("id","")); s=sigmoid((o.get("spam") or {}).get(name))
            if s is not None: S[pid]=s
        if not S: continue
        best=(0.5,0.0,0,0,0)
        for k in range(5,96):
            th=k/100.0; tp=fp=fn=0
            for gid,pid in M.items():
                if gid not in G_map or pid not in S: continue
                y=G_map[gid]; pred=1 if S[pid]>=th else 0
                if y==1 and pred==1: tp+=1
                elif y==0 and pred==1: fp+=1
                elif y==1 and pred==0: fn+=1
            prec=0.0 if (tp+fp)==0 else tp/(tp+fp)
            rec =0.0 if (tp+fn)==0 else tp/(tp+fn)
            F=fbeta(prec,rec,a.beta)
            if F>best[1]: best=(th,F,tp,fp,fn)
        rows.append((name,)+best)
    txt=Path(a.out); txt.parent.mkdir(parents=True,exist_ok=True)
    if not rows:
        txt.write_text(f"[CALIB] {{\"score_name\": \"score_text\", \"threshold\": 0.5}}\n",encoding="utf-8")
        Path("reports_auto/status/spam_calibration.json").write_text(json.dumps({"score_name":"score_text","threshold":0.5},ensure_ascii=False),encoding="utf-8")
        print("BEST name=score_text th=0.5 F=0.0")
        return
    name,th,F,tp,fp,fn=max(rows, key=lambda x:x[2])
    prec=0.0 if (tp+fp)==0 else tp/(tp+fp); rec=0.0 if (tp+fn)==0 else tp/(tp+fn)
    txt.write_text(f"[CALIB] "+json.dumps({"name":name,"threshold":th,"fbeta":F},ensure_ascii=False)+
                   f"\nBEST name={name} th={th}\nF={F:.4f} P={prec:.4f} R={rec:.4f} TP={tp} FP={fp} FN={fn}\n",encoding="utf-8")
    Path("reports_auto/status/spam_calibration.json").write_text(json.dumps({"score_name":name,"threshold":th},ensure_ascii=False),encoding="utf-8")
    print(f"[CALIB] name={name} th={th} F={F:.4f}")
if __name__=="__main__": main()

#!/usr/bin/env python3
import argparse, json, math, statistics as st
def sigmoid(x):
    try: return 1/(1+math.exp(-float(x)))
    except: return None
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--gold",required=True); ap.add_argument("--map",required=True)
    ap.add_argument("--pred_in",required=True); ap.add_argument("--pred_out",required=True)
    ap.add_argument("--status_dir",default="reports_auto/status")
    a=ap.parse_args()
    # 讀 gold→pred 對齊
    import csv
    G2P={}
    for i,row in enumerate(csv.reader(open(a.map,encoding="utf-8"))):
        if i==0: continue
        if row: G2P[row[0]]=row[1]
    # 讀 gold spam
    GOLD={}
    import json
    for ln in open(a.gold,encoding="utf-8"):
        if ln.strip():
            o=json.loads(ln); GOLD[str(o.get("id"))]=int(o.get("label",0))
    # 讀 pred 並重新推導 spam 分數候選
    P=[]
    for ln in open(a.pred_in,encoding="utf-8"):
        if not ln.strip(): continue
        P.append(json.loads(ln))
    # 候選分數：score_text(如已存在其實就以它為 baseline)、sigmoid(pred_ens)、sigmoid(pred_text)
    def cand_scores(sp):
        c={}
        v=sp.get("score_text")
        try:
            v=float(v); 
            if 0.0<=v<=1.0: c["score_text"]=v
        except: pass
        v=sigmoid(sp.get("pred_ens"));   c["sig_pred_ens"]=v if v is not None else None
        v=sigmoid(sp.get("pred_text"));  c["sig_pred_text"]=v if v is not None else None
        return {k:v for k,v in c.items() if v is not None}
    # 搜集配對的 (y, score)；只用 gold 覆蓋到的 pred
    import collections
    pairs=collections.defaultdict(list)
    PID2Y={}
    for gid,pid in G2P.items():
        y=GOLD.get(gid)
        if y is None: continue
        # 找 pred by id
        # 建個小索引
        PID2Y[pid]=y
    idx={o.get("id"):o for o in P}
    for pid,y in PID2Y.items():
        o=idx.get(pid); 
        if not o: continue
        sp=o.get("spam") or {}
        for name,val in cand_scores(sp).items():
            pairs[name].append((y,val))
    # 選擇最佳候選 + 門檻
    def best_threshold(samples):
        # grid 搜索 0.05 步長
        best=(0.0,-1.0,0,0,0) # (th, f1, tp, fp, fn)
        for k in range(0,101,5):
            th=k/100.0
            tp=fp=fn=0
            for y,s in samples:
                pred=1 if s>=th else 0
                if pred==1 and y==1: tp+=1
                elif pred==1 and y==0: fp+=1
                elif pred==0 and y==1: fn+=1
            p = (tp/(tp+fp)) if (tp+fp)>0 else 0.0
            r = (tp/(tp+fn)) if (tp+fn)>0 else 0.0
            f1= (2*p*r/(p+r)) if (p+r)>0 else 0.0
            if f1>best[1]: best=(th,f1,tp,fp,fn)
        return best
    best_name=None; best_pack=None
    for name,samples in pairs.items():
        if not samples: continue
        th,f1,tp,fp,fn=best_threshold(samples)
        if best_pack is None or f1>best_pack[1]:
            best_name=name; best_pack=(th,f1,tp,fp,fn)
    # 寫回校準 + 狀態
    import os; os.makedirs(a.status_dir,exist_ok=True)
    calib={"score_name": best_name or "score_text", "threshold": (best_pack[0] if best_pack else 0.5)}
    open(f"{a.status_dir}/spam_calibration.json","w",encoding="utf-8").write(json.dumps(calib,ensure_ascii=False,indent=2))
    open(f"{a.status_dir}/SPAM_CALIBRATION.txt","w",encoding="utf-8").write(
        f"BEST name={calib['score_name']} th={calib['threshold']}\n")
    # 依最佳名稱覆蓋 score_text
    out=[]
    for o in P:
        sp=o.get("spam") or {}
        c=cand_scores(sp)
        name=calib["score_name"]
        if name in c: sp["score_text"]=c[name]
        o["spam"]=sp; out.append(o)
    tmp=a.pred_out
    with open(tmp,"w",encoding="utf-8") as g:
        for o in out: g.write(json.dumps(o,ensure_ascii=False)+"\n")
    print("[CALIB]",json.dumps(calib,ensure_ascii=False))
if __name__=="__main__": main()

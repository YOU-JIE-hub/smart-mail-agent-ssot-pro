#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, joblib, numpy as np
from pathlib import Path
from sklearn.metrics import classification_report
from _spam_common import text_of, signals

def read_rows(p:Path):
    import json
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--val", required=True)
    ap.add_argument("--model_dir", default="artifacts_prod")
    ap.add_argument("--target_recall", type=float, default=0.95)
    ap.add_argument("--thr_grid", default="0.30,0.32,0.34,0.36,0.38,0.40,0.42,0.44,0.46,0.48,0.50,0.52")
    ap.add_argument("--sig_grid", default="1,2,3,4,5")
    ap.add_argument("--out_dir", default="artifacts_prod")
    ap.add_argument("--out_reports", default="reports_auto")
    args=ap.parse_args()

    rows=read_rows(Path(args.val))
    X=[text_of(r) for r in rows]
    y=np.array([1 if r.get("label")=="spam" or r.get("y")==1 else 0 for r in rows], dtype=int)

    mdlp=Path(args.model_dir)/"model_pipeline.pkl"
    if not mdlp.exists(): mdlp=Path(args.model_dir)/"text_lr_platt.pkl"
    clf=joblib.load(mdlp)

    prob=clf.predict_proba(X)[:,1]
    sig =np.array([signals(r) for r in rows])
    thrs=[float(x) for x in args.thr_grid.split(",")]
    sigs=[int(x) for x in args.sig_grid.split(",")]

    best=None; grid=[]
    for thr in thrs:
        y_text=(prob>=thr).astype(int)
        # 先看 TEXT-only 的 spam recall 是否達標（可選做 soft 限制）
        rep_text=classification_report(y, y_text, output_dict=True, zero_division=0)
        rec_spam=rep_text["1"]["recall"]
        for k in sigs:
            y_rule=(sig>=k).astype(int)
            y_ens=np.maximum(y_text,y_rule)
            rep=classification_report(y, y_ens, output_dict=True, zero_division=0)
            mf1=(rep["0"]["f1-score"]+rep["1"]["f1-score"])/2
            acc=rep["accuracy"]
            ok=(rec_spam>=args.target_recall)  # TEXT recall gate
            grid.append((thr,k,acc,mf1,rec_spam))
            if ok and (best is None or mf1>best[3] or (abs(mf1-best[3])<1e-9 and acc>best[2])):
                best=(thr,k,acc,mf1,rec_spam)
    (thr,k,acc,mf1,rec)=best
    print(f"[BEST] thr={thr:.2f} signals_min={k}  acc={acc:.4f} macroF1={mf1:.4f}  text_recall={rec:.4f}")

    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    Path(args.out_reports).mkdir(parents=True, exist_ok=True)
    j={"threshold":thr,"signals_min":k,"tuned_on":str(Path(args.val)),"acc":acc,"macroF1":mf1,"text_recall":rec}
    Path(args.out_dir+"/ens_thresholds.json").write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding="utf-8")
    with open(Path(args.out_reports)/"prod_sweep.tsv","w",encoding="utf-8") as w:
        w.write("threshold\tsignals_min\tacc\tmacroF1\ttext_recall\n")
        for (a,b,c,d,e) in grid: w.write(f"{a:.2f}\t{b}\t{c:.4f}\t{d:.4f}\t{e:.4f}\n")
    print("[OUT] artifacts_prod/ens_thresholds.json  reports_auto/prod_sweep.tsv")

if __name__=="__main__": main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, joblib, numpy as np
from pathlib import Path
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix, roc_auc_score, average_precision_score
from _spam_common import text_of, signals

def read_rows(p:Path):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

def report(y, yhat):
    P,R,F1,_=precision_recall_fscore_support(y,yhat,average=None,labels=[0,1],zero_division=0)
    cm=confusion_matrix(y,yhat,labels=[0,1]).tolist()
    return dict(macroF1=(F1[0]+F1[1])/2, ham=dict(P=P[0],R=R[0],F1=F1[0]), spam=dict(P=P[1],R=R[1],F1=F1[1]), cm=cm)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--test", default="data/prod_merged/test.jsonl")
    ap.add_argument("--model_dir", default="artifacts_prod")
    ap.add_argument("--out", default="reports_auto/prod_quick_report.md")
    args=ap.parse_args()

    rows=read_rows(Path(args.test))
    X=[text_of(r) for r in rows]
    y=np.array([1 if r.get("label")=="spam" or r.get("y")==1 else 0 for r in rows], dtype=int)

    mdlp=Path(args.model_dir)/"model_pipeline.pkl"
    if not mdlp.exists(): mdlp=Path(args.model_dir)/"text_lr_platt.pkl"
    clf=joblib.load(mdlp)

    prob=clf.predict_proba(X)[:,1]; y_text=(prob>=0.5).astype(int)
    sig=np.array([signals(r) for r in rows]); y_rule=(sig>=3).astype(int)

    import json as _json
    thrj=Path(args.model_dir)/"ens_thresholds.json"
    thr=0.44; sigmin=3
    if thrj.exists():
        try:
            o=_json.loads(thrj.read_text())
            thr=float(o.get("threshold", thr)); sigmin=int(o.get("signals_min",sigmin))
        except Exception: pass
    y_text_thr=(prob>=thr).astype(int)
    y_ens=np.maximum(y_text_thr, (sig>=sigmin).astype(int))

    rt=report(y,y_text); rr=report(y,y_rule); re=report(y,y_ens)
    try:
        auc=roc_auc_score(y,prob); ap=average_precision_score(y,prob)
    except Exception: auc=ap=float("nan")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    def fmt(d): 
        return f"- Macro-F1 **{d['macroF1']:.4f}** | Ham **{d['ham']['P']:.3f}/{d['ham']['R']:.3f}/{d['ham']['F1']:.3f}** | Spam **{d['spam']['P']:.3f}/{d['spam']['R']:.3f}/{d['spam']['F1']:.3f}** | CM **{d['cm']}**"
    Path(args.out).write_text(
f"""# Production Quick Report
- Test: `{args.test}`
- Threshold: **{thr}**, Signals_min: **{sigmin}**
- ROC-AUC: **{auc:.4f}**, PR-AUC: **{ap:.4f}**

## TEXT (thr=0.50)
{fmt(rt)}

## RULE
{fmt(rr)}

## ENSEMBLE (部署建議)
{fmt(re)}
""", encoding="utf-8")

    # 錯誤清單
    fn=[(i,r) for i,(r,yt,ye) in enumerate(zip(rows,y,y_ens)) if yt==1 and ye==0]
    fp=[(i,r) for i,(r,yt,ye) in enumerate(zip(rows,y,y_ens)) if yt==0 and ye==1]
    with open("reports_auto/prod_errors_fn.tsv","w",encoding="utf-8") as w:
        w.write("idx\tsubject\n"); 
        for i,r in fn: w.write(f"{i}\t{(r.get('subject') or '').replace('\t',' ')[:200]}\n")
    with open("reports_auto/prod_errors_fp.tsv","w",encoding="utf-8") as w:
        w.write("idx\tsubject\n");
        for i,r in fp: w.write(f"{i}\t{(r.get('subject') or '').replace('\t',' ')[:200]}\n")

    print("[OUT]", args.out, "reports_auto/prod_errors_fn.tsv", "reports_auto/prod_errors_fp.tsv")

if __name__=="__main__": main()

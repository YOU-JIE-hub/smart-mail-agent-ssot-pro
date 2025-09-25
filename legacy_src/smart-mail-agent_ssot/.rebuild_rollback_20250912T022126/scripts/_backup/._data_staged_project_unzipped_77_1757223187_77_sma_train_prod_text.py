#!/usr/bin/env python3
from __future__ import annotations
import json, argparse, joblib, numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from _sma_common import spam_signals, compute_metrics, dump_eval

def load_jsonl(fp):
    X,y,meta=[],[],[]
    for line in open(fp,encoding="utf-8"):
        e=json.loads(line); meta.append(e)
        X.append((e.get("subject","")+" \n "+e.get("body","")))
        y.append(1 if e.get("label")=="spam" else 0)
    return X, np.array(y), meta

def pick_threshold(meta, y, P, thr_min=0.10, thr_max=0.60, thr_step=0.01):
    # 雙軸掃描：thr ∈ [0.10,0.60]、signals_min ∈ {2,3}
    cand=[]
    thr=thr_min
    while thr<=thr_max+1e-9:
        for sig_min in (2,3):
            yhat=np.array([1 if (spam_signals(e)>=sig_min or p>=thr) else 0 for e,p in zip(meta,P)])
            m=compute_metrics(y,yhat); m.update(thr=round(thr,2), sig_min=sig_min)
            cand.append(m)
        thr+=thr_step
    ok=[c for c in cand if c["spamR"]>=0.95]
    if ok:
        best=max(ok, key=lambda c:(c["macro"], -abs(c["thr"]-0.19)))
    else:
        best=max(cand, key=lambda c:(c["spamR"], c["macro"], -abs(c["thr"]-0.19)))
    return best, cand

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--data_dir", default="data/prod_merged")
    ap.add_argument("--out_dir",  default="artifacts_prod")
    ap.add_argument("--thr_min", type=float, default=0.10)
    ap.add_argument("--thr_max", type=float, default=0.60)
    ap.add_argument("--thr_step", type=float, default=0.01)
    a=ap.parse_args()
    data=Path(a.data_dir); out=Path(a.out_dir); rep=Path("reports_auto")
    out.mkdir(parents=True,exist_ok=True); rep.mkdir(exist_ok=True)

    Xtr,ytr,_=load_jsonl(data/"train.jsonl")
    Xva,yva,Mva=load_jsonl(data/"val.jsonl")
    Xte,yte,Mte=load_jsonl(data/"test.jsonl")

    vect=TfidfVectorizer(analyzer="char", ngram_range=(3,5), min_df=2)
    Xtrv=vect.fit_transform(Xtr)
    base=LogisticRegression(max_iter=1000, C=2.0, class_weight="balanced", n_jobs=None)
    base.fit(Xtrv,ytr)
    cal=CalibratedClassifierCV(base, method="sigmoid", cv="prefit")
    cal.fit(vect.transform(Xva), yva)
    joblib.dump({"vect":vect,"cal":cal}, out/"text_lr_platt.pkl")
    print(f"[OK] model -> {out/'text_lr_platt.pkl'}")

    Pva=cal.predict_proba(vect.transform(Xva))[:,1]
    best, cand = pick_threshold(Mva,yva,Pva, a.thr_min,a.thr_max,a.thr_step)
    json.dump({"threshold":best["thr"],"signals_min":best["sig_min"]}, open(out/"ens_thresholds.json","w"))
    print(f"[SELECT] thr={best['thr']} signals_min={best['sig_min']} spamR={best['spamR']:.3f} macroF1={best['macro']:.4f}")
    with open(rep/"prod_sweep.tsv","w",encoding="utf-8") as w:
        w.write("thr\tsig_min\tmacroF1\thamP\thamR\thamF1\tspamP\tspamR\tspamF1\n")
        for c in cand:
            w.write(f"{c['thr']}\t{c['sig_min']}\t{c['macro']:.4f}\t{c['hamP']:.3f}\t{c['hamR']:.3f}\t{c['hamF1']:.3f}\t{c['spamP']:.3f}\t{c['spamR']:.3f}\t{c['spamF1']:.3f}\n")

    # test：三種模式（text-only / rule-only / ensemble）給面試用對照
    Pte=cal.predict_proba(vect.transform(Xte))[:,1]
    # 1) text-only
    y_text=(Pte>=best["thr"]).astype(int)
    m_text=compute_metrics(yte,y_text)
    dump_eval(rep/"prod_eval_text_only.txt","prod",m_text,best["thr"],999,"text-only")
    # 2) rule-only
    y_rule=np.array([1 if spam_signals(e)>=best["sig_min"] else 0 for e in Mte])
    m_rule=compute_metrics(yte,y_rule)
    dump_eval(rep/"prod_eval_rule_only.txt","prod",m_rule,0.00,best["sig_min"],"rule-only")
    # 3) ensemble
    y_ens=np.array([1 if (spam_signals(e)>=best["sig_min"] or p>=best["thr"]) else 0 for e,p in zip(Mte,Pte)])
    m_ens=compute_metrics(yte,y_ens)
    dump_eval(rep/"prod_eval_ensemble.txt","prod",m_ens,best["thr"],best["sig_min"],"ensemble")
    print("[WRITE] reports_auto/prod_eval_*.txt  &  reports_auto/prod_sweep.tsv")

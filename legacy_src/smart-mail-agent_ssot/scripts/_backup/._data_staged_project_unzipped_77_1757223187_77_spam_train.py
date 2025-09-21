#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, joblib, numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

def read_jsonl(p:Path):
    rows=[]
    with open(p,"r",encoding="utf-8") as f:
        for ln in f:
            if not ln.strip(): continue
            o=json.loads(ln)
            y = 1 if (o.get("label")=="spam" or o.get("y")==1) else 0
            subj = o.get("subject","") or ""
            body = o.get("body","") or ""
            rows.append((f"{subj}\n{body}".strip(), y))
    X=[t for t,_ in rows]; y=np.array([y for _,y in rows], dtype=int)
    return X,y

def train_pipe(C=1.0, calibrate=True):
    vect=TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=1, max_df=1.0)
    base=LogisticRegression(max_iter=2000, C=C, class_weight="balanced", n_jobs=None)
    if calibrate:
        # 直接在 pipeline 裡做 CV-Platt
        clf=CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
    else:
        clf=base
    return Pipeline([("vect", vect), ("clf", clf)])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--val", required=True)
    ap.add_argument("--out_dir", default="artifacts_prod")
    ap.add_argument("--Cs", default="0.5,1.0,2.0")
    ap.add_argument("--no_cal", action="store_true")
    args=ap.parse_args()

    Xtr,ytr=read_jsonl(Path(args.train))
    Xva,yva=read_jsonl(Path(args.val))

    best=(None,-1,None)
    for c in [float(x) for x in args.Cs.split(",")]:
        pipe=train_pipe(C=c, calibrate=(not args.no_cal))
        pipe.fit(Xtr,ytr)
        ypv=pipe.predict(Xva)
        rep=classification_report(yva, ypv, output_dict=True, zero_division=0)
        mf1=(rep["0"]["f1-score"]+rep["1"]["f1-score"])/2
        print(f"[CV] C={c} macroF1={mf1:.4f}")
        if mf1>best[1]: best=(c,mf1,pipe)

    Cstar, mf1, pipe = best
    print(f"[BEST] C={Cstar}  val-macroF1={mf1:.4f}")
    out=Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    # 兩份相容存檔（你現有腳本會找這兩個名字）
    joblib.dump(pipe, out/"model_pipeline.pkl")
    joblib.dump(pipe, out/"text_lr_platt.pkl")
    print(f"[SAVED] {out/'model_pipeline.pkl'}  {out/'text_lr_platt.pkl'}")

if __name__ == "__main__":
    main()

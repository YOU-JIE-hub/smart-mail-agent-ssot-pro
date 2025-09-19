#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, joblib, sys
from pathlib import Path
import numpy as np
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

def load_jsonl(fp):
    X, y, ids = [], [], []
    with open(fp, encoding="utf-8") as f:
        for line in f:
            e=json.loads(line)
            X.append((e.get("subject","")+" \n "+e.get("body","")))
            y.append(1 if e["label"]=="spam" else 0)
            ids.append(e.get("id"))
    return X, np.array(y), ids

ap=argparse.ArgumentParser()
ap.add_argument("--data", required=True)
ap.add_argument("--model", default="artifacts_sa_text/text_lr_platt.pkl")
ap.add_argument("--thresholds", default="artifacts_sa_text/text_thresholds.json")
ap.add_argument("--out", default="")
a=ap.parse_args()

X, y, _ = load_jsonl(a.data)
clf = joblib.load(a.model)
thr = json.loads(Path(a.thresholds).read_text())["threshold"]

proba = clf.predict_proba(X)[:,1]
pred  = (proba>=thr).astype(int)

P,R,F1,_ = precision_recall_fscore_support(y, pred, average=None, labels=[0,1], zero_division=0)
macro = F1.mean()
cm = confusion_matrix(y, pred, labels=[0,1]).tolist()

lines = [
    f"[SPAM][EVAL] macro_f1={macro:.4f} thr={thr:.2f} w_rule=0.00 w_llm=0.00",
    f"[SPAM][EVAL] ham  P/R/F1 = {P[0]:.3f}/{R[0]:.3f}/{F1[0]:.3f}",
    f"[SPAM][EVAL] spam P/R/F1 = {P[1]:.3f}/{R[1]:.3f}/{F1[1]:.3f}",
    f"[SPAM][EVAL] confusion = {cm}",
]
txt = "\n".join(lines)
print(txt)
if a.out:
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(txt)

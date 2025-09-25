#!/usr/bin/env python3
from __future__ import annotations
import json, argparse, joblib
from pathlib import Path
import numpy as np
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

def load_jsonl(fp):
    X, y, ids = [], [], []
    with open(fp, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            X.append((e.get("subject","")+" \n "+e.get("body","")))
            y.append(1 if e["label"]=="spam" else 0)
            ids.append(e.get("id"))
    return X, np.array(y), ids

ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True)   # test 或任何 jsonl
ap.add_argument("--model", default="artifacts_sa_text/text_lr_platt.pkl")
ap.add_argument("--out",   default="reports_auto/text_eval.txt")
ap.add_argument("--target_recall", type=float, default=0.95)
a = ap.parse_args()

X, y, _ = load_jsonl(a.data)
clf = joblib.load(a.model)
proba = clf.predict_proba(X)[:,1]

rows=[]
for thr in [i/100 for i in range(0,100)]:
    pred = (proba>=thr).astype(int)
    P,R,F1,_ = precision_recall_fscore_support(y, pred, average=None, labels=[0,1], zero_division=0)
    macro = F1.mean()
    rows.append({"thr":thr, "macroF1":macro, "hamP":P[0], "hamR":R[0], "hamF1":F1[0], "spamP":P[1], "spamR":R[1], "spamF1":F1[1]})

# 選門檻：先滿足 spamR≥target；若無，取 spamR 最大再看 macroF1
ok = [r for r in rows if r["spamR"]>=a.target_recall]
if ok: pick = max(ok, key=lambda r:(r["macroF1"], -abs(r["thr"]-0.28)))
else:  pick = max(rows, key=lambda r:(r["spamR"], r["macroF1"]))

pred = (proba>=pick["thr"]).astype(int)
cm = confusion_matrix(y, pred, labels=[0,1]).tolist()

Path(a.out).write_text(
    "\n".join([
        f"[TEXT][EVAL] macro_f1={pick['macroF1']:.4f} thr={pick['thr']:.2f}",
        f"[TEXT][EVAL] ham  P/R/F1 = {pick['hamP']:.3f}/{pick['hamR']:.3f}/{pick['hamF1']:.3f}",
        f"[TEXT][EVAL] spam P/R/F1 = {pick['spamP']:.3f}/{pick['spamR']:.3f}/{pick['spamF']:.3f}" if 'spamF' in pick else f"[TEXT][EVAL] spam P/R/F1 = {pick['spamP']:.3f}/{pick['spamR']:.3f}/{pick['spamF1']:.3f}",
        f"[TEXT][EVAL] confusion = {cm}"
    ])
)
print(f"[SELECT] thr={pick['thr']:.2f} spamR={pick['spamR']:.3f} macroF1={pick['macroF1']:.4f}")
print(f"[WRITE] {a.out}")
# 也順手輸出 sweep 表
from pathlib import Path
import csv
with open("reports_auto/text_sweep.tsv","w",newline="") as w:
    fw=csv.writer(w,delimiter="\t")
    fw.writerow(["thr","macroF1","hamP","hamR","hamF1","spamP","spamR","spamF1"])
    for r in rows: fw.writerow([r[k] for k in ["thr","macroF1","hamP","hamR","hamF1","spamP","spamR","spamF1"]])
print("[WRITE] reports_auto/text_sweep.tsv")

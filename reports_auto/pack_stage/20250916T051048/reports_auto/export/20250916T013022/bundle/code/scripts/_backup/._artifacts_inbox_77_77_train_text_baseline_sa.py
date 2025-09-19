#!/usr/bin/env python3
from __future__ import annotations
import json, argparse, joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight
import numpy as np

def load_jsonl(fp):
    X, y, ids = [], [], []
    with open(fp, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            txt = (e.get("subject","") + " \n " + e.get("body",""))
            X.append(txt)
            y.append(1 if e["label"]=="spam" else 0)
            ids.append(e.get("id"))
    return X, np.array(y), ids

ap = argparse.ArgumentParser()
ap.add_argument("--train", default="data/spam_sa/train.jsonl")
ap.add_argument("--val",   default="data/spam_sa/val.jsonl")
ap.add_argument("--outdir", default="artifacts_sa_text")
a = ap.parse_args()

Path(a.outdir).mkdir(parents=True, exist_ok=True)

# 讀資料
Xtr, ytr, _ = load_jsonl(a.train)
Xv,  yv,  _ = load_jsonl(a.val)

# 特徵：字元 3–5gram（對雜訊拼寫/網址變體很有韌性）
vec = TfidfVectorizer(analyzer="char", ngram_range=(3,5), min_df=3, max_features=300000)
# 先用 class_weight=balanced 的 LR 拿到可分界模型
lr = LogisticRegression(max_iter=2000, n_jobs=-1, class_weight="balanced")
pipe = Pipeline([("tfidf", vec), ("lr", lr)])
pipe.fit(Xtr, ytr)

# Platt scaling（sigmoid 校準）
cal = CalibratedClassifierCV(pipe, method="sigmoid", cv="prefit")
cal.fit(Xv, yv)

# 驗證集簡報
from sklearn.metrics import precision_recall_fscore_support
proba = cal.predict_proba(Xv)[:,1]
pred = (proba>=0.5).astype(int)
P,R,F1, _ = precision_recall_fscore_support(yv, pred, average=None, labels=[0,1])
macroF1 = F1.mean()
print(f"[TEXT][VAL] macro_f1={macroF1:.4f}  ham P/R/F1={P[0]:.3f}/{R[0]:.3f}/{F1[0]:.3f}  spam P/R/F1={P[1]:.3f}/{R[1]:.3f}/{F1[1]:.3f}")
print(confusion_matrix(yv, pred))

# 存檔
joblib.dump(cal, f"{a.outdir}/text_lr_platt.pkl")
print(f"[OK] saved -> {a.outdir}/text_lr_platt.pkl")

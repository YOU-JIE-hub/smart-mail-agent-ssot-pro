from __future__ import annotations
import argparse, json, pathlib, hashlib
from typing import List, Dict, Any
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
import joblib

SEED = 42
def read_jsonl(p: pathlib.Path) -> list[dict]:
    out=[]
    with p.open("r", encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if ln: out.append(json.loads(ln))
    return out

def sha256_head(p: pathlib.Path, n=1024*1024) -> str:
    h=hashlib.sha256()
    with p.open("rb") as f: h.update(f.read(n))
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="data/spam/train.jsonl")
    ap.add_argument("--test",  default="data/spam/dev.jsonl")
    ap.add_argument("--outdir", default="models/spam/artifacts/v1")
    args = ap.parse_args()

    outdir = pathlib.Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    train = read_jsonl(pathlib.Path(args.train))
    test  = read_jsonl(pathlib.Path(args.test)) if pathlib.Path(args.test).exists() else None
    if not train: raise SystemExit("no training data")

    X = [ d.get("text") or (d.get("subject","")+" "+d.get("body","")) for d in train ]
    y = [ int(d.get("y",0)) for d in train ]
    if test:
        Xte = [ d.get("text") or (d.get("subject","")+" "+d.get("body","")) for d in test ]
        yte = [ int(d.get("y",0)) for d in test ]
    else:
        X, Xte, y, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)

    pipe = Pipeline([
        ("vec", TfidfVectorizer(ngram_range=(1,2), min_df=2, max_df=0.9)),
        ("clf", LogisticRegression(max_iter=200, class_weight="balanced", n_jobs=None, random_state=SEED)),
    ])
    pipe.fit(X, y)

    yhat = pipe.predict(Xte)
    rep   = classification_report(yte, yhat, output_dict=True, zero_division=0)
    try:
        score = pipe.predict_proba(Xte)[:,1]
        ap = float(average_precision_score(yte, score))
        auc = float(roc_auc_score(yte, score))
    except Exception:
        ap = auc = None

    pkl = outdir / "spam_rules_lr.pkl"
    joblib.dump(pipe, pkl)

    (outdir / "metrics.json").write_text(json.dumps({"n":len(X)+len(Xte),"report":rep,"ap":ap,"auc":auc}, ensure_ascii=False, indent=2), "utf-8")
    (outdir / "manifest.json").write_text(json.dumps({"spam_rules_lr.pkl":{"size":pkl.stat().st_size,"sha256_head":sha256_head(pkl)}}, ensure_ascii=False, indent=2), "utf-8")
    print(f"[OK] saved -> {pkl}")
if __name__=="__main__":
    main()

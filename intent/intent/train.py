from __future__ import annotations
import argparse, json, pathlib, time, hashlib, os, random, numpy as np
from typing import List, Dict, Any
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
import joblib

from vendor.rules_features import rules_feat, feature_schema_from_fitted

SEED = 42
random.seed(SEED); np.random.seed(SEED)

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
    ap.add_argument("--train", default="data/intent/train.jsonl")
    ap.add_argument("--test",  default="data/intent/dev.jsonl")
    ap.add_argument("--outdir", default="models/intent/artifacts/v1")
    args = ap.parse_args()

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    train = read_jsonl(pathlib.Path(args.train))
    test  = read_jsonl(pathlib.Path(args.test)) if pathlib.Path(args.test).exists() else None
    if not train:
        raise SystemExit("no training data")

    X = [r.get("text","") for r in train]
    y = [r.get("label","") for r in train]
    if test:
        Xte = [r.get("text","") for r in test]
        yte = [r.get("label","") for r in test]
    else:
        X, Xte, y, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)

    feat = rules_feat()
    clf = CalibratedClassifierCV(base_estimator=LinearSVC(), method="sigmoid", cv=3)
    pipe = Pipeline([("features", feat), ("clf", clf)])
    pipe.fit(X, y)

    y_pred = pipe.predict(Xte)
    rep = classification_report(yte, y_pred, output_dict=True, zero_division=0)

    # features schema
    try:
        feat_schema = feature_schema_from_fitted(pipe.named_steps["features"])
    except Exception:
        feat_schema = None

    pkl_path = outdir / "intent_pro_cal.pkl"
    joblib.dump({"pipeline": pipe}, pkl_path)

    (outdir / "features.schema.json").write_text(json.dumps(feat_schema, ensure_ascii=False, indent=2), "utf-8")
    (outdir / "metrics.json").write_text(json.dumps({"n":len(X)+len(Xte),"test_report":rep}, ensure_ascii=False, indent=2), "utf-8")
    (outdir / "manifest.json").write_text(json.dumps({"intent_pro_cal.pkl":{"size":pkl_path.stat().st_size,"sha256_head":sha256_head(pkl_path)}}, ensure_ascii=False, indent=2), "utf-8")
    print(f"[OK] saved -> {pkl_path}")

if __name__=="__main__":
    main()

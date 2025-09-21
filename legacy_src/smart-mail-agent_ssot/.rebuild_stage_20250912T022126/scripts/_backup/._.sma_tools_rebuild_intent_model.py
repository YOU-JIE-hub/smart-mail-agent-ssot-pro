#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, pickle, sys, types
from pathlib import Path
from collections import Counter
from scipy import sparse

# ========= shim: 把 sma_tools 做成「套件」，並提供子模組 =========
class ZeroPad:
    def __init__(self, n_features=0, n=0, **kw): self.n_features = int(n_features or n or 0)
    def fit(self, X, y=None): return self
    def transform(self, X): return sparse.csr_matrix((len(X), self.n_features), dtype="float64")

class DictFeaturizer:
    def __init__(self, **kw): pass
    def fit(self, X, y=None): return self
    def transform(self, X): return sparse.csr_matrix((len(X), 0), dtype="float64")

pkg = types.ModuleType("sma_tools"); pkg.__path__ = []  # 標記為 package
sys.modules.setdefault("sma_tools", pkg)

m1 = types.ModuleType("sma_tools.sk_zero_pad");     m1.ZeroPad = ZeroPad
m2 = types.ModuleType("sma_tools.dict_featurizer"); m2.DictFeaturizer = DictFeaturizer
sys.modules["sma_tools.sk_zero_pad"]     = m1
sys.modules["sma_tools.dict_featurizer"] = m2
setattr(pkg, "sk_zero_pad", m1)
setattr(pkg, "dict_featurizer", m2)
# ===================================================================

def is_pipeline(o):
    return hasattr(o,"predict") and (hasattr(o,"transform") or hasattr(o,"steps") or hasattr(o,"named_steps"))

def load_or_rebuild(src: Path):
    obj = pickle.load(open(src, "rb"))
    if is_pipeline(obj):
        return obj
    if isinstance(obj, dict):
        for k in ("pipeline","sk_pipeline","pipe"):
            v = obj.get(k)
            if v is not None and is_pipeline(v):
                return v
        from sklearn.pipeline import Pipeline, FeatureUnion
        parts=[]
        for name in ("word_vec","char_vec","pad","features","feats"):
            if name in obj and obj[name] is not None:
                parts.append((name, obj[name]))
        if not parts:
            raise RuntimeError("dict 內沒有可用特徵（word_vec/char_vec/pad）")
        feats = FeatureUnion(parts)
        return Pipeline([("features", feats), ("clf", obj["clf"])])
    raise RuntimeError("來源 pkl 不是 Pipeline，也不是可組回的 dict")

def read_train(path: Path):
    X,Y=[],[]
    with open(path,"r",encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln)
            y=o.get("label") or o.get("intent") or o.get("y")
            t=o.get("text") or (o.get("subject","")+"\n"+o.get("body",""))
            if y and t:
                X.append((t or "").strip()); Y.append(y)
    return X,Y

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from_pkl", required=True)
    ap.add_argument("--train",    required=True)
    ap.add_argument("--save",     required=True)
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--C", type=float, default=1.0)
    args = ap.parse_args()

    src  = Path(args.from_pkl)
    trn  = Path(args.train)
    out  = Path(args.save)
    if not src.exists(): sys.exit(f"[FATAL] from_pkl 不存在: {src}")
    if not trn.exists(): sys.exit(f"[FATAL] train 不存在: {trn}")

    pipe = load_or_rebuild(src)

    if args.calibrate:
        from sklearn.svm import LinearSVC
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.pipeline import Pipeline
        feats = getattr(pipe, "named_steps", {}).get("features") or getattr(pipe, "named_steps", {}).get("feats")
        base  = getattr(pipe, "named_steps", {}).get("clf")
        if isinstance(base, LinearSVC):
            base.set_params(C=args.C)
            clf = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
            pipe = Pipeline([("features", feats), ("clf", clf)])

    X,Y = read_train(trn)
    print(f"[FIT] n={len(X)} dist={Counter(Y)}")
    pipe.fit(X,Y)
    out.parent.mkdir(parents=True, exist_ok=True)
    pickle.dump({"pipeline": pipe}, open(out,"wb"))
    print("[SAVED]", out.resolve())

if __name__ == "__main__":
    main()

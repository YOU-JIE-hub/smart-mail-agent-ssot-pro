#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, pickle, sys, types
from pathlib import Path
import numpy as np
from scipy import sparse

# ========= shim: sma_tools 作為 package =========
class ZeroPad:
    def __init__(self, n_features=0, n=0, **kw): self.n_features = int(n_features or n or 0)
    def fit(self, X, y=None): return self
    def transform(self, X): return sparse.csr_matrix((len(X), self.n_features), dtype="float64")
class DictFeaturizer:
    def __init__(self, **kw): pass
    def fit(self, X, y=None): return self
    def transform(self, X): return sparse.csr_matrix((len(X), 0), dtype="float64")

pkg = types.ModuleType("sma_tools"); pkg.__path__ = []
sys.modules.setdefault("sma_tools", pkg)
m1 = types.ModuleType("sma_tools.sk_zero_pad");     m1.ZeroPad = ZeroPad
m2 = types.ModuleType("sma_tools.dict_featurizer"); m2.DictFeaturizer = DictFeaturizer
sys.modules["sma_tools.sk_zero_pad"]     = m1
sys.modules["sma_tools.dict_featurizer"] = m2
setattr(pkg, "sk_zero_pad", m1)
setattr(pkg, "dict_featurizer", m2)
# ================================================

def is_pipeline(o):
    return hasattr(o, "predict") and (hasattr(o,"transform") or hasattr(o,"steps") or hasattr(o,"named_steps"))

def load_pipeline(pkl: Path):
    obj = pickle.load(open(pkl, "rb"))
    if is_pipeline(obj): return obj
    if isinstance(obj, dict):
        for k in ("pipeline","sk_pipeline","pipe"):
            v = obj.get(k)
            if v is not None and is_pipeline(v): return v
        from sklearn.pipeline import Pipeline, FeatureUnion
        parts=[]
        for name in ("word_vec","char_vec","pad","features","feats"):
            if name in obj and obj[name] is not None:
                parts.append((name, obj[name]))
        if not parts:
            raise RuntimeError("dict 內沒有可用的特徵transformer（word_vec/char_vec/pad）")
        feats = FeatureUnion(parts)
        return Pipeline([("features", feats), ("clf", obj["clf"])])
    raise RuntimeError(f"{pkl.name} 不是可推論的 Pipeline，也無法從 dict 組回")

def read_test(path: Path):
    rows=[]
    with open(path,"r",encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln)
            y=o.get("label") or o.get("intent") or o.get("y")
            t=o.get("text") or (o.get("subject","")+"\n"+o.get("body",""))
            rows.append((o.get("id") or o.get("doc_id") or "", o.get("lang") or "", y, (t or "").strip()))
    return rows

def cmatrix(y_true, y_pred, labels):
    idx = {lab:i for i,lab in enumerate(labels)}
    M = np.zeros((len(labels),len(labels)), dtype=int)
    for a,b in zip(y_true,y_pred):
        if a in idx and b in idx: M[idx[a], idx[b]] += 1
    return M

def prf_counts(y_true, y_pred, labels):
    out={}
    for lab in labels:
        tp=fp=fn=0
        for yt,yp in zip(y_true,y_pred):
            tp += (yt==lab and yp==lab)
            fp += (yt!=lab and yp==lab)
            fn += (yt==lab and yp!=lab)
        P = tp/(tp+fp) if (tp+fp)>0 else 0.0
        R = tp/(tp+fn) if (tp+fn)>0 else 0.0
        F = (2*P*R/(P+R)) if (P+R)>0 else 0.0
        out[lab]={"tp":tp,"fp":fp,"fn":fn,"P":P,"R":R,"F1":F}
    acc = sum(yt==yp for yt,yp in zip(y_true,y_pred))/len(y_true)
    macro = float(np.mean([out[lab]["F1"] for lab in labels])) if labels else 0.0
    return acc, macro, out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--test",  required=True)
    ap.add_argument("--out_prefix", required=True)
    args = ap.parse_args()

    model_path = Path(args.model)
    test_path  = Path(args.test)
    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    pipe = load_pipeline(model_path)
    rows = read_test(test_path)
    X=[t for _,_,_,t in rows]; Y=[y for _,_,y,_ in rows]
    y_pred = pipe.predict(X)
    labels = sorted(list({y for y in Y if y is not None}))

    acc, macro, by = prf_counts(Y, y_pred, labels)
    M = cmatrix(Y, y_pred, labels)

    p_eval = Path(str(out_prefix) + "_eval.txt")
    p_conf = Path(str(out_prefix) + "_confusion.tsv")
    p_errs = Path(str(out_prefix) + "_errors.tsv")

    with open(p_eval,"w",encoding="utf-8") as fo:
        fo.write(f"pairs={len(Y)}\nAccuracy={acc:.4f}\nMacroF1={macro:.4f}\n")
        for lab in labels:
            d=by[lab]
            fo.write(f"{lab}: P={d['P']:.4f} R={d['R']:.4f} F1={d['F1']:.4f} (tp={d['tp']},fp={d['fp']},fn={d['fn']})\n")

    with open(p_conf,"w",encoding="utf-8") as fo:
        fo.write("label\t" + "\t".join(labels) + "\n")
        for i,lab in enumerate(labels):
            fo.write(lab + "\t" + "\t".join(str(int(x)) for x in M[i]) + "\n")

    with open(p_errs,"w",encoding="utf-8") as fo:
        fo.write("id\tlang\tgold\tpred\ttext\n")
        for i,(idx,lang,yt,txt) in enumerate(rows):
            yp = y_pred[i]
            if yp != yt:
                san = (txt or "").replace("\t"," ").replace("\n"," ")
                fo.write(f"{idx}\t{lang}\t{yt}\t{yp}\t{san[:500]}\n")

    print("[OUT]", p_eval, p_conf, p_errs)

if __name__ == "__main__":
    main()

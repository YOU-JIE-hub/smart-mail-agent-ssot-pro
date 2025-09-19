from __future__ import annotations
import os, json, sys, joblib, numpy as np
from scipy import sparse as sp

PKL = os.environ.get("SMA_INTENT_ML_PKL", "artifacts/intent_pipeline_aligned.pkl")
XS = ["報價與交期", "技術支援", "發票抬頭", "退訂連結"]

def as_csr(x):
    if sp.issparse(x): return x.tocsr()
    if isinstance(x, np.ndarray): return sp.csr_matrix(x if x.ndim==2 else x.reshape(1,-1))
    raise TypeError(f"non-numeric branch output: {type(x).__name__}")

def feature_dims(pre):
    dims={}
    if hasattr(pre, "transformer_list"):
        for name,tr in pre.transformer_list:
            try: dims[name] = as_csr(tr.transform(XS)).shape[1]
            except Exception as e: dims[name] = f"ERR:{type(e).__name__}"
    return dims

pipe = joblib.load(PKL)
steps = dict(getattr(pipe,"steps",[]))
clf = pipe if not hasattr(pipe,"steps") else list(steps.values())[-1]
expected = getattr(clf, "n_features_in_", None)
pre = steps.get("features") or steps.get("pre") or steps.get("union")
dims = feature_dims(pre) if pre is not None else {}
sum_dim = sum(v for v in dims.values() if isinstance(v,int))
print(json.dumps({
  "pkl": PKL,
  "steps": [(n, t.__class__.__name__) for n,t in getattr(pipe,"steps",[])],
  "branch_dims": dims,
  "sum_branch_dims": sum_dim,
  "clf_expected": expected,
  "pass": (expected is None) or (sum_dim == expected)
}, ensure_ascii=False, indent=2))

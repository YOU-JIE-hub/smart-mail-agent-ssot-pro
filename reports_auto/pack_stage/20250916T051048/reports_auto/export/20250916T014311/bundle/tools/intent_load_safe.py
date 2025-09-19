from __future__ import annotations
import os, sys, json, joblib
from collections import OrderedDict
import numpy as np
from scipy import sparse as sp

TO_ZH = {"biz_quote":"報價","tech_support":"技術支援","complaint":"投訴","policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"}
def _short(x): return x.__class__.__name__
def _as_csr(X):
    if sp.issparse(X): return X.tocsr()
    if isinstance(X, np.ndarray): return sp.csr_matrix(X if X.ndim==2 else X.reshape(1, -1))
    raise TypeError(f"non-numeric branch output: {type(X)}")

def _sum_feature_dim(fu, samples):
    dims=OrderedDict()
    for name, est in getattr(fu,"transformer_list",[]):
        try: dims[name]=_as_csr(est.transform(samples)).shape[1]
        except Exception: dims[name]=None
    return dims

def load_pipe(pkl:str):
    obj=joblib.load(pkl)
    if isinstance(obj, dict):
        for k in ("pipe","model","clf","estimator"):
            if k in obj and hasattr(obj[k],"predict"): return obj[k], obj
        for v in obj.values():
            if hasattr(v,"predict"): return v, obj
        raise RuntimeError("dict 包裝裡找不到可推論的 pipeline")
    return obj, None

def align_zero_pad(pipe):
    steps=getattr(pipe,"steps",[])
    if not steps: return pipe, {}
    last=steps[-1][1]
    expect=getattr(last,"n_features_in_", None)
    if expect is None: return pipe, {}
    fu=None
    for n,est in steps:
        if _short(est)=="FeatureUnion": fu=est; break
    if fu is None: return pipe, {}
    xs=["a","b","c","d"]
    dims=_sum_feature_dim(fu,xs)
    cur=sum([(d or 0) for d in dims.values()])
    pad_key=[n for n,_ in getattr(fu,"transformer_list",[]) if "pad" in n or "zero" in n]
    pad_key=pad_key[0] if pad_key else None
    changed={}
    if pad_key and cur!=expect:
        need=max(expect-cur,0)
        pad=dict(fu.transformer_list)[pad_key]
        if hasattr(pad,"width"):
            pad.width=int(need)
            fu.set_params(**{f"{pad_key}__width":int(need)})
            changed["pad.width"]=need
    return pipe, {"expected":expect,"dims":dims,"changed":changed}

def main():
    pkl=os.environ.get("SMA_INTENT_ML_PKL","").strip()
    out=os.environ.get("SMA_INTENT_ALIGNED_OUT","").strip()
    if not pkl or not os.path.exists(pkl): print("[FATAL] model not found:", pkl); sys.exit(2)
    pipe, meta=load_pipe(pkl)
    print("steps:", [(n,_short(e)) for n,e in getattr(pipe,"steps",[])])
    if hasattr(pipe,"classes_"): print("classes:", list(pipe.classes_))
    pipe2, info=align_zero_pad(pipe)
    if info:
        print("[align]", json.dumps({
            "expected": info.get("expected"),
            "sum_before": sum([(d or 0) for d in info.get("dims",{}).values()]),
            "after_pad_width": info.get("changed",{}).get("pad.width","unchanged")
        }, ensure_ascii=False))
    xs=["您好，想詢問報價與交期","請協助開立三聯發票抬頭","需要技術支援，附件無法上傳"]
    try:
        ys=pipe2.predict(xs)
        print("sample_pred:", [f"{x} -> {y}/{TO_ZH.get(str(y),str(y))}" for x,y in zip(xs,ys)])
    except Exception as e:
        print("[SMOKE_FAIL]", type(e).__name__, str(e))
    if out: joblib.dump(pipe2,out,compress=3); print("[SAVED]", out)

if __name__=="__main__": main()

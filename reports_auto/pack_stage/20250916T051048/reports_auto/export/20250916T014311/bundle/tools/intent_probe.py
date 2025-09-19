from __future__ import annotations
import os, sys, json, types, importlib
import numpy as np
from scipy import sparse as sp
import joblib

TO_ZH = {
    "biz_quote":"報價","tech_support":"技術支援","complaint":"投訴",
    "policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"
}

def short(x): return x.__class__.__name__

def as_csr(X):
    if sp.issparse(X): return X.tocsr()
    if isinstance(X, np.ndarray):
        return sp.csr_matrix(X if X.ndim==2 else X.reshape(1,-1))
    raise TypeError(f"unsupported branch output: {type(X)}")

def feature_dim(est, samples):
    """試跑單一 transformer，回傳 (n, m) 的 m"""
    try:
        Y = est.transform(samples)
        Y = as_csr(Y)
        return Y.shape[1]
    except Exception as e:
        return None

def walk_feature_union(est):
    """在 Pipeline/FeatureUnion 裡把每個分支拿出來 (path, transformer)"""
    out = []
    # Pipeline
    if hasattr(est, "steps"):
        cur = est
        for name, sub in cur.steps:
            # 只深入到 features/FeatureUnion 這一層
            if short(sub) == "FeatureUnion":
                fu = sub
                for n, tr in getattr(fu, "transformer_list", []):
                    out.append((f"features.{n}", tr))
            # 也保留非 FeatureUnion 末端
        return out
    # 直接是 FeatureUnion
    if short(est) == "FeatureUnion":
        for n, tr in getattr(est, "transformer_list", []):
            out.append((f"features.{n}", tr))
    return out

def expected_n_features(final_est):
    # LinearSVC / LogisticRegression / Linear models
    for attr in ("coef_", "coefs_"):
        if hasattr(final_est, attr):
            A = getattr(final_est, attr)
            # LinearSVC: coef_.shape == (n_classes or 1, n_features)
            return int(A.shape[-1])
    # Calibrated + base_estimator
    if hasattr(final_est, "base_estimator_"):
        return expected_n_features(final_est.base_estimator_)
    return None

def main():
    pkl = os.environ.get("SMA_INTENT_ML_PKL", "")
    if not pkl or not os.path.exists(pkl):
        print(json.dumps({"fatal":"SMA_INTENT_ML_PKL not found","path":pkl}, ensure_ascii=False)); sys.exit(2)

    pipe = joblib.load(pkl)
    print("steps:", [(n, short(e)) for n,e in getattr(pipe, "steps", [])])
    # 取 classifier 末端
    clf = dict(getattr(pipe, "steps", [])) .get("clf") or dict(getattr(pipe, "steps", [])).get("cal") or pipe
    want = expected_n_features(clf)

    # 掃 features 分支
    branches = walk_feature_union(pipe)
    if not branches:
        print("[WARN] no FeatureUnion branches detected; proceeding anyway.")

    samples = ["A", "B", "C", "D"]  # dummy english tokens;只看 shape
    dims = {}
    pad_like = []
    for path, tr in branches:
        dim = feature_dim(tr, samples)
        dims[path] = dim
        mod = getattr(tr, "__module__", "")
        if mod.startswith("sma_tools") or "ZeroPad" in short(tr):
            pad_like.append((path, tr))
    s = sum(d for d in dims.values() if isinstance(d, int))
    print("[before] branch dims:", json.dumps({k:v for k,v in dims.items()}, ensure_ascii=False))
    print("clf_expected:", want, "  sum_before:", s)

    # 對齊：如果有缺口，優先把第一個 pad-like 分支補到剛好
    if isinstance(want, int) and isinstance(s, int) and want != s and pad_like:
        gap = want - s
        path, tr = pad_like[0]
        # 盡量使用既有屬性
        w_now = int(getattr(tr, "width", 1) or 1)
        setattr(tr, "width", max(1, w_now + gap))
        # 重新量測
        dims[path] = feature_dim(tr, samples)
        s = sum(d for d in dims.values() if isinstance(d, int))
        print("[after ] branch dims:", json.dumps({k:v for k,v in dims.items()}, ensure_ascii=False))
        print("sum_after:", s)

    # 中文樣本 smoke test（不修改語意分支，僅 pad 對齊）
    xs = [
        "您好，想詢問報價與交期",
        "請協助開立三聯發票抬頭",
        "需要技術支援，附件無法上傳",
        "這封是垃圾郵件免費賺錢"
    ]
    try:
        ys = pipe.predict(xs)
        for s,y in zip(xs, ys):
            print("  ", s, "->", f"{y} / {TO_ZH.get(str(y), str(y))}")
    except Exception as e:
        print("[PRED_FAIL]", type(e).__name__, str(e))

    # 顯示類別空間
    classes = getattr(clf, "classes_", None)
    if classes is not None:
        print("classes:", list(map(str, classes)))

    # 可選：輸出一份 aligned 版本（不覆蓋原檔）
    out = os.environ.get("SMA_INTENT_ALIGNED_OUT", "")
    if out:
        try:
            joblib.dump(pipe, out)
            print("[SAVED]", out)
        except Exception as e:
            print("[SAVE_FAIL]", type(e).__name__, str(e))

if __name__ == "__main__":
    main()

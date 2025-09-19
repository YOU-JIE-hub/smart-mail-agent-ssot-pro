from __future__ import annotations
import os, sys, json, types, importlib
from pathlib import Path
import joblib, numpy as np
from scipy import sparse as sp
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report

ROOT = Path(os.environ.get("SMA_ROOT", Path.cwd()))
BUNDLE_PKL = ROOT / "intent" / "artifacts" / "intent_pro_cal.pkl"
OUT_PKL    = ROOT / "artifacts" / "intent_from_bundle_aligned.pkl"
DATA_JSONL = ROOT / "data" / "intent_eval" / "dataset.cleaned.jsonl"

TO_ZH = {"biz_quote":"報價","tech_support":"技術支援","complaint":"投訴","policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"}
ZH2EN = {v:k for k,v in TO_ZH.items()}

# 讓 pickle 找到專案內自定義符號（不改檔）
import __main__ as M
for modname in [
    "smart_mail_agent.intent.rules",
    "smart_mail_agent.intent.features",
    "smart_mail_agent.intent.feats",
    "smart_mail_agent.intent.utils",
    "scripts.sma_eval_intent_with_rules",
]:
    try:
        m = importlib.import_module(modname)
        for k,v in vars(m).items():
            if k.startswith("__") or isinstance(v, types.ModuleType): continue
            if not hasattr(M,k): setattr(M,k,v)
    except Exception:
        pass

# 裝載 zip 內的 dict 並重組
def to_csr(X):
    from scipy import sparse as _sp
    if _sp.issparse(X): return X.tocsr()
    import numpy as _np
    if isinstance(X, _np.ndarray): return _sp.csr_matrix(X if X.ndim==2 else X.reshape(1,-1))
    raise TypeError(f"non-array branch output: {type(X)}")

def branch_dim(tr, sample_texts):
    try:
        Y = tr.transform(sample_texts)
        return to_csr(Y).shape[1]
    except Exception:
        return None

def expect_dim_of_clf(clf):
    if hasattr(clf,"coef_"): return clf.coef_.shape[1]
    if hasattr(clf,"n_features_in_"): return int(clf.n_features_in_)
    return None

def assemble_from_dict(d: dict):
    for k in ("pipeline","pipe"):
        if k in d and isinstance(d[k], Pipeline):
            return d[k]

    feats = None
    if "features" in d and isinstance(d["features"], FeatureUnion):
        feats = d["features"]
    else:
        parts=[]
        for key in ("word","char","vec_word","vec_char"):
            if key in d and isinstance(d[key], TfidfVectorizer):
                parts.append((key, d[key]))
        if "pad" in d and hasattr(d["pad"], "transform"):
            parts.append(("pad", d["pad"]))
        if parts:
            feats = FeatureUnion(parts)
    if feats is None:
        raise RuntimeError(f"無法從字典組出 features；dict keys={list(d.keys())}")

    clf = None
    for key in ("clf","svm","svc","estimator","model"):
        if key in d and hasattr(d[key], "fit") and hasattr(d[key], "predict"):
            clf = d[key]; break
    if clf is None:
        raise RuntimeError("找不到可用分類器（clf/svm/svc/estimator/model）")

    pipe = Pipeline([("features", feats), ("clf", clf)])
    cal = d.get("cal")
    if isinstance(cal, CalibratedClassifierCV):
        pipe = Pipeline([("features", feats), ("cal", cal)])
    return pipe

def fix_zero_pad_width(pipe: Pipeline, sample_texts):
    steps = dict(pipe.steps)
    last = steps.get("clf") or steps.get("cal")
    clf = last if not isinstance(last, CalibratedClassifierCV) else last.estimator
    need = expect_dim_of_clf(clf)
    if need is None: return pipe
    feats = steps.get("features")
    if not isinstance(feats, FeatureUnion): return pipe

    dims = {}
    for name, tr in feats.transformer_list:
        dims[name] = branch_dim(tr, sample_texts)
    got = sum(d for d in dims.values() if isinstance(d,int))
    gap = (need - got) if (need is not None and got is not None) else 0

    # pad 存在則調；否則補
    tmap = dict(feats.transformer_list)
    if "pad" in tmap:
        pad = tmap["pad"]
        if hasattr(pad,"width"):
            pad.width = max(int(gap),1) if gap!=0 else max(int(getattr(pad,"width",1) or 1),1)
        new_list = [(n, (pad if n=="pad" else tr)) for n,tr in feats.transformer_list]
        steps["features"] = FeatureUnion(new_list)
        return Pipeline([(k, steps[k]) for k,_ in pipe.steps])

    # 無 pad → 補 vendor ZeroPad
    try:
        from sma_tools.sk_zero_pad import ZeroPad
    except Exception:
        class ZeroPad:
            def __init__(self, width=1, dtype=np.float64, **kw):
                self.width = int(width) if width else 1
                self.dtype = np.float64
            def fit(self,X,y=None): return self
            def transform(self,X):
                import numpy as _np
                from scipy import sparse as _sp
                return _sp.csr_matrix((len(X), self.width), dtype=self.dtype)
    pad = ZeroPad(width=max(int(gap),1))
    new_list = list(feats.transformer_list) + [("pad", pad)]
    steps["features"] = FeatureUnion(new_list)
    return Pipeline([(k, steps[k]) for k,_ in pipe.steps])

def main():
    if not BUNDLE_PKL.exists():
        print(f"[FATAL] 找不到模型：{BUNDLE_PKL}"); sys.exit(2)

    obj = joblib.load(BUNDLE_PKL)
    pipe = assemble_from_dict(obj) if isinstance(obj, dict) else obj
    samples = ["您好，想詢問報價與交期","請協助開立三聯發票抬頭","需要技術支援協助，附件連不上","退訂連結在此"]
    pipe = fix_zero_pad_width(pipe, samples)
    _ = pipe.predict(["測試"])  # smoke

    # 簡單資料集評估（若存在）
    if DATA_JSONL.exists():
        xs, gold_zh = [], []
        with open(DATA_JSONL,'r',encoding='utf-8') as f:
            for l in f:
                l=l.strip()
                if not l: continue
                d=json.loads(l)
                xs.append(d.get("text") or d.get("content") or d.get("utterance") or "")
                gold_zh.append(str(d.get("label") or d.get("intent") or ""))
        pred_en = pipe.predict(xs)
        pred_zh = [TO_ZH.get(str(y), str(y)) for y in pred_en]

        from collections import Counter
        C = Counter(pred_zh)
        print("pred_top:", C.most_common(6))

        # 針對可映射子集的報告
        mask   = [g in ZH2EN for g in gold_zh]
        y_true = [ZH2EN[g] for g,m in zip(gold_zh,mask) if m]
        y_pred = [p for p,m in zip(pred_en,mask) if m]
        if y_true:
            print("subset_acc:", round(sum(int(a==b) for a,b in zip(y_pred,y_true))/len(y_true), 4),
                  " n=", len(y_true))
            try:
                labels = sorted(set(y_true) | set(y_pred))
                print(classification_report(y_true, y_pred, labels=labels, zero_division=0))
            except Exception:
                pass

    joblib.dump(pipe, OUT_PKL)
    print("[SAVED]", str(OUT_PKL))

if __name__ == "__main__":
    main()

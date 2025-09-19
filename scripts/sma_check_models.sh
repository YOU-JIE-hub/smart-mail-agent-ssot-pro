#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
cd "/home/youjie/projects/smart-mail-agent_ssot" || exit 1

python - <<'PY'
import pathlib, sys, json, joblib, numpy as np
print("== INTENT ==")
# stubs 先放進 __main__ 給 joblib 找
from types import SimpleNamespace
try:
    from scipy import sparse as sp
except Exception as e:
    print("  [FATAL] SciPy 未安裝"); sys.exit(1)
def rules_feat(texts):
    KW={"biz_quote":["報價","quote","quotation"],"tech_support":["錯誤","error","bug","crash"],
        "complaint":["投訴","抱怨"],"policy_qa":["隱私","政策","GDPR","DPA"],"profile_update":["更新","變更","email","電話"]}
    rows,cols,data=[],[],[]
    for i,s in enumerate([t.lower() for t in texts]):
        j=0
        for k in ("biz_quote","tech_support","complaint","policy_qa","profile_update"):
            rows.append(i); cols.append(j); data.append(1 if any(w in s for w in KW[k]) else 0); j+=1
        rows.append(i); cols.append(j); data.append(1 if ("http://" in s or "https://" in s or "附件" in s) else 0)
    return sp.csr_matrix((data,(rows,cols)), shape=(len(texts),6), dtype="float64")
class ZeroPad:
    def __init__(self,n_features=0,**kw): self.n_features=int(n_features or 0)
    def fit(self,*a,**k): return self
    def transform(self,X): return sp.csr_matrix((X.shape[0], self.n_features), dtype="float64")
class DictFeaturizer:
    def __init__(self,**kw): pass
    def fit(self,*a,**k): return self
    def transform(self,X): return sp.csr_matrix((X.shape[0],0), dtype="float64")

mp=pathlib.Path("artifacts/intent_pro_cal.pkl")
if not mp.exists():
    print("  [MISS] artifacts/intent_pro_cal.pkl 不存在")
else:
    try:
        obj=joblib.load(mp)
    except Exception as e:
        print("  [ERROR] 載入失敗：", e); sys.exit(0)

    from sklearn.pipeline import Pipeline
    def first(o, seen=set()):
        if id(o) in seen: return None
        seen.add(id(o))
        if isinstance(o, Pipeline): return o
        if isinstance(o, dict):
            for k in ("pipe","pipeline","model","clf"):
                v=o.get(k)
                if isinstance(v, Pipeline): return v
            if "vect" in o and ("cal" in o or "clf" in o):
                return Pipeline([("vect", o["vect"]), ("clf", o.get("cal", o.get("clf")))])
            for v in o.values():
                p=first(v, seen)
                if p is not None: return p
        if isinstance(o,(list,tuple)):
            for v in o:
                p=first(v, seen)
                if p is not None: return p
        return None
    pipe=first(obj)
    if pipe is None:
        print("  [FATAL] 找不到 Pipeline")
    else:
        clf=pipe.steps[-1][1]
        labels=list(getattr(clf,"classes_",[]))
        print("  classes:", labels)
        from sklearn.calibration import CalibratedClassifierCV
        base=clf
        if isinstance(clf, CalibratedClassifierCV):
            base = clf.calibrated_classifiers_[0].estimator
        need = int(base.coef_.shape[1]) if hasattr(base,"coef_") else None
        pre=Pipeline(pipe.steps[:-1])
        texts=["測試資料一"]
        shapes=[]
        try: shapes.append(("str_list", pre.transform(texts)))
        except: pass
        try: shapes.append(("dict_text_subject_body", pre.transform([{"text":texts[0],"subject":"","body":texts[0]}])))
        except: pass
        try: shapes.append(("dict_text", pre.transform([{"text":texts[0]}])))
        except: pass
        try:
            arr=np.array(texts, dtype=object).reshape(-1,1)
            shapes.append(("array_2d", pre.transform(arr)))
        except: pass
        best = max(shapes, key=lambda z:(z[1].nnz>0, z[1].shape[1])) if shapes else None
        if best:
            how, Xt = best
            print(f"  feature_dim: need={need} cur={Xt.shape[1]} (transform_by={how}, nnz={Xt.nnz})")
        else:
            print("  [FATAL] transform 皆失敗")

print("== SPAM ==")
mp=pathlib.Path("artifacts_prod/model_pipeline.pkl")
if mp.exists():
    obj=joblib.load(mp)
    from sklearn.pipeline import Pipeline
    assert isinstance(obj, Pipeline)
    labels=list(getattr(obj.steps[-1][1],"classes_",["?"]))
    print("  classes:", labels, "| predict_proba:", hasattr(obj.steps[-1][1],"predict_proba"))
else:
    print("  [MISS] artifacts_prod/model_pipeline.pkl 不存在")

print("== KIE ==")
cur=pathlib.Path("artifacts/releases/kie_xlmr/current")
if cur.exists():
    need=["model.safetensors","tokenizer.json","config.json"]
    miss=[f for f in need if not (cur/f).exists()]
    print("  path:", str(cur.resolve()))
    print("  files_ok:", ("YES" if not miss else f"missing {miss}"))
else:
    print("  [MISS] artifacts/releases/kie_xlmr/current 不存在")
PY

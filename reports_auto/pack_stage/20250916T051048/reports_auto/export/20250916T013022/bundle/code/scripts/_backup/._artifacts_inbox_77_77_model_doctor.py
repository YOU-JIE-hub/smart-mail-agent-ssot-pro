#!/usr/bin/env python3
from __future__ import annotations
import json, joblib, sklearn, sys
from pathlib import Path
from sklearn.pipeline import Pipeline, make_pipeline

PKL_IN  = Path("artifacts_prod/text_lr_platt.pkl")
PKL_OUT = Path("artifacts_prod/model_pipeline.pkl")
META    = Path("artifacts_prod/model_meta.json")
THRJS   = Path("artifacts_prod/ens_thresholds.json")

def to_pipeline(obj):
    if hasattr(obj, "predict_proba"):   # 已是可用 pipeline/estimator
        return obj, "as-is"
    if isinstance(obj, dict):
        # 常見：{'vect': TfidfVectorizer, 'cal': CalibratedClassifierCV}
        if "vect" in obj and "cal" in obj:
            return make_pipeline(obj["vect"], obj["cal"]), "rebuild(vect+cal)"
        if "pipeline" in obj and hasattr(obj["pipeline"], "predict_proba"):
            return obj["pipeline"], "use(dict['pipeline'])"
        # 退路：找第一個能 predict_proba 的
        for k,v in obj.items():
            if hasattr(v, "predict_proba"):
                return v, f"use(dict['{k}'])"
    raise TypeError("Cannot build a predict_proba pipeline from pkl")

def meta_of(pipe):
    meta={"sklearn": sklearn.__version__}
    try:
        vect = pipe.named_steps.get("tfidf", pipe.named_steps.get("vect"))
        if vect:
            meta["vectorizer"]={"class": type(vect).__name__, "ngram_range": getattr(vect,"ngram_range",None),
                                "analyzer": getattr(vect,"analyzer",None), "min_df": getattr(vect,"min_df",None),
                                "max_df": getattr(vect,"max_df",None)}
    except: pass
    try:
        cal = pipe.named_steps.get("cal")
        if cal:
            meta["calibrator"]=type(cal).__name__
            be = getattr(cal, "base_estimator", None) or getattr(cal, "estimator", None)
            if be is None and hasattr(cal, "calibrated_classifiers_"):
                try: be = cal.calibrated_classifiers_[0].base_estimator
                except: pass
            if be is not None:
                meta["base_estimator"]=type(be).__name__
                coef = getattr(be, "coef_", None)
                if coef is not None: meta["coef_shape"]=getattr(coef, "shape", None)
    except: pass
    if THRJS.exists():
        try: meta["threshold"]=json.loads(THRJS.read_text())["threshold"]
        except: pass
    return meta

obj = joblib.load(PKL_IN)
pipe, how = to_pipeline(obj)
# 煙霧測試（避免一維/二維 shape 錯誤）
_ = pipe.predict_proba(["Subject: smoke\nbody"])[:,1]
joblib.dump(pipe, PKL_OUT)
META.write_text(json.dumps({"built_via": how, **meta_of(pipe)}, ensure_ascii=False, indent=2))
print("[OK] normalized pipeline ->", PKL_OUT)
print(META.read_text())

from __future__ import annotations
import os, sys, json, traceback, time, joblib, types, importlib
from pathlib import Path
import numpy as np
from scipy import sparse as sp

# 外層已建立 LOGDIR；這裡再建一層保險
BASE = Path("reports_auto/intent_import")
BASE.mkdir(parents=True, exist_ok=True)
LOGDIR = BASE / time.strftime("%Y%m%dT%H%M%S")
LOGDIR.mkdir(parents=True, exist_ok=True)
RUN = (LOGDIR / "run.log").open("w", encoding="utf-8")
def log(*a): print(*a, file=RUN, flush=True); print(*a, flush=True)

def inject_project_symbols():
    import __main__ as M, types, importlib
    for mod in [
        "smart_mail_agent.intent.rules",
        "smart_mail_agent.intent.features",
        "smart_mail_agent.intent.feats",
        "smart_mail_agent.intent.utils",
        "scripts.sma_eval_intent_with_rules",
    ]:
        try:
            m = importlib.import_module(mod)
            for k,v in vars(m).items():
                if k.startswith("__") or isinstance(v, types.ModuleType): continue
                if not hasattr(M,k): setattr(M,k,v)
        except Exception as e:
            log("[inject_skip]", mod, type(e).__name__, e)

def unwrap_model(obj):
    if hasattr(obj, "predict"): return obj, None
    if isinstance(obj, dict):
        for k in ("pipe","pipeline","estimator","clf","model"):
            if k in obj and hasattr(obj[k], "predict"):
                return obj[k], obj
    return obj, None

def feat_dims(est, xs):
    dims = {}
    if hasattr(est, "transformer_list"):
        for name, sub in est.transformer_list:
            try:
                Y = sub.transform(xs)
                if sp.issparse(Y): Y = Y.tocsr()
                elif isinstance(Y, np.ndarray): Y = sp.csr_matrix(Y if Y.ndim==2 else Y.reshape(1,-1))
                else: raise TypeError(f"{name} -> {type(Y).__name__}")
                dims[name] = Y.shape[1]
            except Exception as e:
                dims[name] = f"ERR:{type(e).__name__}"
    return dims

def expected_dim_from(est):
    clf = est
    if hasattr(est, "steps"): clf = est.steps[-1][1]
    if hasattr(clf, "n_features_in_"): return int(clf.n_features_in_)
    if hasattr(clf, "base_estimator") and hasattr(clf.base_estimator, "n_features_in_"):
        return int(clf.base_estimator.n_features_in_)
    return None

def main():
    inject_project_symbols()
    # 1) 挑你 zip 解到 intent/artifacts 的那顆
    intent_dir = Path("intent/artifacts")
    for name in ("intent_pro_cal.pkl","intent_pipeline_fixed.pkl","intent_pipeline.pkl"):
        p = intent_dir / name
        if p.exists():
            pkl = p
            break
    else:
        log("[FATAL] 找不到 intent/artifacts/*.pkl"); (LOGDIR/"last_trace.txt").write_text("missing pkl",encoding="utf-8"); sys.exit(2)
    log("[PKL]", pkl)

    # 2) 載入 + unwrap
    try:
        obj = joblib.load(pkl)
    except Exception as e:
        log("[LOAD_FAIL]", type(e).__name__, e)
        (LOGDIR/"last_trace.txt").write_text(traceback.format_exc(), encoding="utf-8"); raise
    est, meta = unwrap_model(obj)
    if not hasattr(est, "predict"):
        log("[FATAL] unwrap 後不可 predict"); (LOGDIR/"last_trace.txt").write_text("unwrap_not_predictable",encoding="utf-8"); sys.exit(3)
    log("[OK] estimator:", est.__class__.__name__)

    # 3) 對齊 pad（只動 ZeroPad 不動其他）
    pre = None
    if hasattr(est,"steps"):
        d = dict(est.steps); pre = d.get("features") or d.get("pre") or d.get("union")
    xs = ["報價與交期","技術支援","發票抬頭","退訂連結"]
    dims = feat_dims(pre, xs) if pre is not None else {}
    exp = expected_dim_from(est)
    num = sum(v for v in dims.values() if isinstance(v,int))
    delta = None if exp is None or not num else exp - num
    log("[BRANCH_DIMS]", json.dumps(dims, ensure_ascii=False))
    log("[EXPECTED]", exp, " [SUM]", num, " [DELTA]", delta)

    if delta and hasattr(pre,"transformer_list"):
        for i,(n,sub) in enumerate(pre.transformer_list):
            nn = n.lower()
            if any(k in nn for k in ("pad","zero")) and hasattr(sub,"width"):
                try:
                    old = int(getattr(sub,"width",1) or 1)
                    setattr(sub,"width", old + delta)
                    pre.transformer_list[i] = (n, sub)
                    log("[PAD_FIX]", n, f"{old} -> {old+delta}")
                    break
                except Exception as e:
                    log("[PAD_FIX_FAIL]", n, type(e).__name__, e)

    # 4) 存 aligned
    OUT = Path("artifacts/intent_pipeline_aligned.pkl")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        joblib.dump(est, OUT)
        log("[SAVED]", str(OUT))
    except Exception as e:
        log("[SAVE_FAIL]", type(e).__name__, e)
        (LOGDIR/"last_trace.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise

    # 5) 煙囪測
    zh = {"biz_quote":"報價","tech_support":"技術支援","complaint":"投訴","policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"}
    tests = ["您好，想詢問報價與交期","請協助開立三聯發票抬頭","需要技術支援協助，附件連不上","退訂連結在此"]
    try:
        pred = est.predict(tests)
        for s,y in zip(tests,pred):
            print("  ", s, "->", f"{y} / {zh.get(str(y),str(y))}")
        (LOGDIR/"sample_pred.json").write_text(json.dumps({"samples":tests,"pred":[str(x) for x in pred]}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log("[PRED_FAIL]", type(e).__name__, e)
        (LOGDIR/"last_trace.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise

    RUN.close()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # 確保一定落地 traceback
        Path("reports_auto/intent_import/last_fatal.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise

from __future__ import annotations
import os, sys, re, json, time, types, traceback
from pathlib import Path
from typing import Any, Tuple, Dict, List

TS=time.strftime("%Y%m%dT%H%M%S")
OUT_DIR=Path("reports_auto/debug"); OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG  = OUT_DIR/f"ml_probe_{TS}.log"
JOUT = OUT_DIR/f"ml_probe_{TS}.json"

def log(*a):
    msg=" ".join(str(x) for x in a)
    print(msg)
    LOG.write_text((LOG.read_text() if LOG.exists() else "")+msg+"\n", encoding="utf-8")

def alias_sma_features():
    import importlib
    src=Path("src").resolve()
    if str(src) not in sys.path: sys.path.insert(0, str(src))
    try:
        sf = importlib.import_module("sma_features")
    except Exception:
        # 最兜底 shim（不預期會用到）
        mod=types.ModuleType("sma_features")
        def _ensure_list(X):
            if isinstance(X,(str,bytes,dict)): return [X]
            try: iter(X); return list(X)
            except Exception: return [X]
        def rules_feat(X,*a,**k): return [{} for _ in _ensure_list(X)]
        def prio_bias(X,*a,**k):
            import numpy as np
            return np.zeros((len(_ensure_list(X)),0), dtype="float64")
        mod.rules_feat=rules_feat; mod.prio_feat=prio_bias; mod.bias_feat=prio_bias
        sf=mod
    sys.modules["sma_features"]=sf
    sys.modules["__main__"]=sf

def find_model() -> Path:
    cand=os.environ.get("SMA_INTENT_ML_PKL")
    if cand and Path(cand).exists(): return Path(cand)
    for p in [Path("artifacts/intent_pro_cal.pkl"),
              Path("../smart-mail-agent_ssot/artifacts/intent_pro_cal.pkl").resolve()]:
        if p.exists(): return p
    raise SystemExit("[FATAL] 找不到模型（設 SMA_INTENT_ML_PKL 或放 artifacts/intent_pro_cal.pkl）")

def load_pipeline(pkl: Path):
    import joblib
    alias_sma_features()
    return joblib.load(pkl)

def describe_X(X: Any) -> Dict[str, Any]:
    info={"type": type(X).__name__}
    try:
        import numpy as np
        from scipy import sparse
        if isinstance(X, (list, tuple)):
            info["len"]=len(X)
            if len(X)>0:
                x0=X[0]; info["item0.type"]=type(x0).__name__
                if isinstance(x0, tuple): info["item0.tuple_types"]=[type(t).__name__ for t in x0]
                if isinstance(x0, dict):  info["item0.keys"]=sorted(list(x0.keys()))[:10]
                if isinstance(x0,(str,bytes)): info["item0.preview"]=str(x0)[:80]
        elif sparse.issparse(X): info.update({"sparse":True,"shape":tuple(X.shape),"dtype":str(X.dtype)})
        elif isinstance(X, np.ndarray): info.update({"ndarray":True,"shape":tuple(X.shape),"dtype":str(X.dtype)})
        elif hasattr(X,"shape"):
            try: info["shape"]=tuple(X.shape)
            except Exception: pass
    except Exception:
        pass
    return info

def describe_out(Y: Any) -> Dict[str, Any]:
    return describe_X(Y)

def instrument(obj, path="root", summary=None):
    # --- 關鍵修補：穩健初始化 ---
    if summary is None or "nodes" not in summary:
        summary={"nodes":[]}
    summary["nodes"].append({"path": path, "type": obj.__class__.__name__})

    import sklearn.pipeline as skpl
    import sklearn.compose as skco
    import functools

    def wrap(instance, method_name):
        if not hasattr(instance, method_name): return
        orig=getattr(instance, method_name)
        if hasattr(orig, "__wrapped_probe__"): return
        @functools.wraps(orig)
        def wrapper(*args, **kwargs):
            try: X = args[1] if len(args)>=2 else kwargs.get("X", None)
            except Exception: X = None
            log(f"[CALL] {path}.{instance.__class__.__name__}.{method_name} IN", json.dumps(describe_X(X), ensure_ascii=False))
            try:
                Y=orig(*args, **kwargs)
                log(f"[RET ] {path}.{instance.__class__.__name__}.{method_name} OUT", json.dumps(describe_out(Y), ensure_ascii=False))
                return Y
            except Exception as e:
                log(f"[EXC ] {path}.{instance.__class__.__name__}.{method_name} -> {type(e).__name__}: {e}")
                log(traceback.format_exc(limit=3))
                raise
        setattr(wrapper, "__wrapped_probe__", True)
        setattr(instance, method_name, types.MethodType(wrapper, instance))

    if isinstance(obj, skpl.Pipeline):
        for name, step in obj.steps:
            instrument(step, f"{path}|{name}", summary)
        wrap(obj,"predict"); wrap(obj,"predict_proba")
        return summary

    if isinstance(obj, skpl.FeatureUnion):
        for name, tr in obj.transformer_list:
            instrument(tr, f"{path}|{name}", summary)
        wrap(obj,"transform"); wrap(obj,"fit_transform")
        return summary

    if isinstance(obj, skco.ColumnTransformer):
        for name, tr, cols in obj.transformers:
            instrument(tr, f"{path}|{name}", summary)
        wrap(obj,"transform"); wrap(obj,"fit_transform")
        return summary

    for mn in ("transform","fit_transform","predict","predict_proba"):
        wrap(obj, mn)
    return summary

def sample_inputs() -> List[Tuple[str, Any]]:
    e={"subject":"報價 單價:100 數量:2", "body":"ticket TS-1234 規則詢問 資料異動 order ORD-9"}
    combo=f"{e['subject']} {e['body']}"
    return [
        ("dict+text", [{"subject":e["subject"],"body":e["body"],"text":combo}]),
        ("string",    [combo]),
        ("tuple",     [(e["subject"], e["body"])]),
    ]

def run_variants(est):
    results=[]
    for tag, X in sample_inputs():
        ok=True; err=None
        log(f"\n[TRY ] variant={tag}  X0={json.dumps(describe_X(X), ensure_ascii=False)}")
        try:
            try: _=est.predict_proba(X)
            except Exception: _=est.predict(X)
        except Exception as e:
            ok=False; err=f"{type(e).__name__}: {e}"
        log(f"[DONE] variant={tag} ok={ok} err={err}")
        results.append({"variant":tag, "ok":ok, "err":err})
    return results

def pick_estimator(top) -> tuple[Any, dict]:
    meta={"top_type": type(top).__name__, "unwrapped": False, "unwrap_key": None}
    if isinstance(top, dict):
        keys=list(top.keys())
        meta["top_keys"]=keys
        for k in ("pipeline","pipe","estimator","model"):
            if k in top:
                meta["unwrapped"]=True; meta["unwrap_key"]=k
                return top[k], meta
        # 兜底：找出第一個帶 predict/predict_proba 的 value
        for k,v in top.items():
            if hasattr(v,"predict") or hasattr(v,"predict_proba"):
                meta["unwrapped"]=True; meta["unwrap_key"]=k
                return v, meta
    return top, meta

def main():
    LOG.write_text("", encoding="utf-8")
    pkl=find_model()
    log(f"[INFO] model={pkl}")
    alias_sma_features()
    top=load_pipeline(pkl)

    # 結構文字
    try: rep=str(top)[:10000]
    except Exception: rep=top.__class__.__name__
    log("[STRUCT]\n"+rep)

    est, meta = pick_estimator(top)
    if meta.get("unwrapped"):
        log(f"[INFO] top-level is dict -> unwrap by key: {meta['unwrap_key']} ({type(est).__name__})")
    else:
        log(f"[INFO] estimator type: {type(est).__name__}")

    summary={}
    instrument(est, "root", summary)
    results=run_variants(est)

    out={"model": str(pkl), "meta": meta, "results": results, "nodes": summary.get("nodes", [])}
    JOUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"\n[SAVED] {LOG}")
    log(f"[SAVED] {JOUT}")

if __name__=="__main__":
    main()

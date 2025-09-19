from __future__ import annotations
import os, sys, json, glob, types, importlib, time
from pathlib import Path
import joblib, numpy as np
from scipy import sparse as sp
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.calibration import CalibratedClassifierCV

ROOT = Path.cwd()
INTENT_ROOT = ROOT / "intent"
DATA_JSONL = ROOT / "data" / "intent_eval" / "dataset.cleaned.jsonl"
OUT = ROOT / "artifacts" / f"intent_from_bundle_aligned_{time.strftime('%Y%m%dT%H%M%S')}.pkl"

TO_ZH = {"biz_quote":"報價","tech_support":"技術支援","complaint":"投訴",
         "policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"}

def _print_env():
    import sklearn, scipy
    info = {
      "python": sys.version.split()[0],
      "numpy": np.__version__,
      "scipy": scipy.__version__,
      "sklearn": sklearn.__version__,
      "cwd": str(ROOT),
      "PYTHONPATH": os.environ.get("PYTHONPATH",""),
    }
    print("=== ENV ==="); print(json.dumps(info, ensure_ascii=False, indent=2))

def _find_candidates():
    # 常見命名優先
    pri = []
    for pat in [
        "artifacts/intent_pipeline_fixed.pkl",
        "artifacts/intent_pro_cal.pkl",
        "artifacts/intent_pro_cal_fixed.pkl",
        "intent_pipeline_fixed.pkl",
        "intent_pro_cal.pkl",
        "intent_pro_cal_fixed.pkl",
        "**/*.pkl",
    ]:
        pri += list(INTENT_ROOT.glob(pat))
    seen = []
    out = []
    for p in pri:
        if p.exists():
            k = str(p.resolve())
            if k not in seen:
                seen.append(k); out.append(p)
    return out[:50]

def _inject_project_symbols():
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

def _ensure_vendor_on_path():
    vendor = str((ROOT/"vendor").resolve())
    if vendor not in sys.path:
        sys.path.insert(0, vendor)

def _safe_load(p):
    try:
        return joblib.load(p), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

def _to_csr(X):
    if sp.issparse(X): return X.tocsr()
    if isinstance(X, np.ndarray): return sp.csr_matrix(X if X.ndim==2 else X.reshape(1,-1))
    raise TypeError(f"branch returned {type(X)}")

def _branch_dim(tr, samples):
    try:
        return _to_csr(tr.transform(samples)).shape[1]
    except Exception:
        return None

def _expected_dim(clf_or_cal):
    est = clf_or_cal
    if isinstance(est, CalibratedClassifierCV):
        est = est.estimator
    if hasattr(est, "coef_"): return est.coef_.shape[1]
    if hasattr(est, "n_features_in_"): return int(est.n_features_in_)
    return None

def _as_pipeline(obj):
    if isinstance(obj, Pipeline): return obj
    if isinstance(obj, dict):
        feats = obj.get("features")
        if isinstance(feats, FeatureUnion):
            last = obj.get("cal") or obj.get("clf") or obj.get("model") or obj.get("estimator")
            if last is None: raise RuntimeError("dict 缺少分類器")
            return Pipeline([("features", feats), ("cal" if isinstance(last, CalibratedClassifierCV) else "clf", last)])
        # 退而求其次：用常見鍵重組
        parts=[]
        for k in ("word","char","vec_word","vec_char"):
            if k in obj: parts.append((k, obj[k]))
        if "pad" in obj: parts.append(("pad", obj["pad"]))
        if not parts: raise RuntimeError("dict 找不到 features")
        fu = FeatureUnion(parts)
        last = obj.get("cal") or obj.get("clf") or obj.get("model") or obj.get("estimator")
        if last is None: raise RuntimeError("dict 缺少分類器")
        return Pipeline([("features", fu), ("cal" if isinstance(last, CalibratedClassifierCV) else "clf", last)])
    raise RuntimeError(f"不支援的物件型別：{type(obj)}")

def _fix_pad(pipe, samples):
    steps = dict(pipe.steps)
    feats = steps.get("features")
    last  = steps.get("cal") or steps.get("clf")
    need  = _expected_dim(last)
    if not isinstance(feats, FeatureUnion) or need is None:
        return pipe, {"need": need, "sum": None, "gap": None, "changed": False}

    dims = {n: _branch_dim(tr, samples) for n,tr in feats.transformer_list}
    s = sum([d for d in dims.values() if isinstance(d,int)])
    gap = (need - s) if (s is not None) else None

    changed = False
    if gap and gap != 0:
        tmap = dict(feats.transformer_list)
        if "pad" in tmap and hasattr(tmap["pad"], "width"):
            tmap["pad"].width = int(gap) if gap>0 else max(1, int(getattr(tmap["pad"],"width",1)))
            newlist = [(n, (tmap["pad"] if n=="pad" else tr)) for n,tr in feats.transformer_list]
        else:
            from sma_tools.sk_zero_pad import ZeroPad
            newlist = list(feats.transformer_list) + [("pad", ZeroPad(width=int(gap) if gap>0 else 1))]
        steps["features"] = FeatureUnion(newlist)
        pipe = Pipeline([(k, steps[k]) for k,_ in pipe.steps])
        changed = True

    return pipe, {"need": need, "sum": s, "gap": (None if gap is None else int(gap)), "changed": changed, "dims": dims}

def main():
    _print_env()
    _ensure_vendor_on_path()
    _inject_project_symbols()

    if not INTENT_ROOT.exists():
        print(f"[FATAL] 找不到 intent/ 目錄：{INTENT_ROOT}")
        sys.exit(2)

    cands = _find_candidates()
    if not cands:
        print("[FATAL] intent/ 內找不到任何 .pkl 候選"); sys.exit(2)

    print("\n=== 掃描候選 ===")
    for p in cands[:10]: print(" -", p)

    chosen = None
    load_errs = {}
    for p in cands:
        obj, err = _safe_load(p)
        if err:
            load_errs[str(p)] = err
            continue
        try:
            pipe = _as_pipeline(obj)
            # smoke transform
            pipe.named_steps.get("features", pipe).transform(["測試"])
            chosen = (p, pipe); break
        except Exception as e:
            load_errs[str(p)] = f"pipeline 組裝/變換失敗: {type(e).__name__}: {e}"

    if not chosen:
        print("\n[FAIL] 無法載入任何候選，主要原因：")
        for k,v in list(load_errs.items())[:8]:
            print(" *", k, "->", v)
        sys.exit(2)

    p, pipe = chosen
    print("\n[LOAD] 使用：", p)

    samples = ["您好，想詢問報價與交期","請協助開立三聯發票抬頭","需要技術支援協助，附件連不上","退訂連結在此"]
    pipe, info = _fix_pad(pipe, samples)

    # 詳細列印
    print("\n=== 對齊摘要 ===")
    print(json.dumps(info, ensure_ascii=False, indent=2))

    # 逐句測
    try:
        ys = pipe.predict(samples)
        zh = [TO_ZH.get(str(y), str(y)) for y in ys]
        print("\n=== SAMPLE PRED ===")
        for s,y in zip(samples, zh): print("  ", s, "->", y)
    except Exception as e:
        print("\n[WARN] sample predict 失敗：", f"{type(e).__name__}: {e}")

    # 評估（若有資料）
    if DATA_JSONL.exists():
        xs, gold_zh = [], []
        with open(DATA_JSONL,'r',encoding='utf-8') as f:
            for l in f:
                l=l.strip()
                if not l: continue
                import json
                d=json.loads(l)
                xs.append(d.get("text") or d.get("content") or d.get("utterance") or "")
                gold_zh.append(str(d.get("label") or d.get("intent") or ""))
        pred_en = pipe.predict(xs)
        pred_zh = [TO_ZH.get(str(y), str(y)) for y in pred_en]
        from collections import Counter
        print("\n[pred_top]", Counter(pred_zh).most_common(6))

    joblib.dump(pipe, OUT)
    print("\n[SAVED]", OUT)

if __name__ == "__main__":
    main()

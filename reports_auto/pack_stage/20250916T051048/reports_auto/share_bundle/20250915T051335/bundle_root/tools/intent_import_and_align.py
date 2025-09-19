from __future__ import annotations
import os, sys, json, time, traceback, types, importlib, importlib.machinery as mach
from pathlib import Path
import joblib, numpy as np
from scipy import sparse as sp

LOGDIR = Path(os.environ.get("LOGDIR", "reports_auto/intent_import/"+time.strftime("%Y%m%dT%H%M%S")))
LOGDIR.mkdir(parents=True, exist_ok=True)

def wjson(name, obj):
    (LOGDIR/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def env_snapshot():
    import sklearn, scipy, numpy
    return dict(
        python = sys.version.split()[0],
        numpy  = numpy.__version__,
        scipy  = scipy.__version__,
        sklearn= sklearn.__version__,
        joblib = joblib.__version__,
        cwd    = os.getcwd(),
        PYTHONPATH = os.environ.get("PYTHONPATH","")
    )

def find_code_root():
    for d in [Path("intent/intent"), Path("intent")]:
        if (d/"artifacts").exists(): return d
    return None

def find_pkl(code_root: Path):
    cands = [code_root/"artifacts/intent_pro_cal.pkl",
             code_root/"artifacts/intent_pipeline_fixed.pkl",
             code_root/"artifacts/intent_pipeline.pkl"]
    for p in cands:
        if p.exists(): return p
    # fallback: 任何 .pkl
    xs = sorted((code_root/"artifacts").glob("*.pkl"))
    return xs[0] if xs else None

def copy_rules_feat(code_root: Path):
    # 掃描 code_root 下所有 .py，找定義 rules_feat 的檔案，複製到 vendor/rules_features.py
    import re, shutil
    vendor = Path("vendor/rules_features.py")
    best = None
    for py in code_root.rglob("*.py"):
        try:
            txt = py.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"\ndef\s+rules_feat\s*\(", txt):
                best = py
                break
        except: pass
    if best:
        vendor.write_text(best.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        return str(vendor)
    return None

def bind_rules_feat_alias(missing_mod: str):
    """
    建立一個跟 pickle 期望"相同名稱"的 alias 模組，把 rules_feat 指到 vendor.rules_features.rules_feat。
    """
    try:
        spec = mach.ModuleSpec(missing_mod, loader=None, is_package=False)
        m = types.ModuleType(missing_mod); m.__spec__ = spec
        import importlib.util
        rf = importlib.import_module("rules_features") if "rules_features" in sys.modules else importlib.import_module("vendor.rules_features".replace("/","."))
    except Exception:
        rf = importlib.import_module("rules_features")  # 如果 vendor 已在 sys.path 頂層
    import __main__ as M
    if hasattr(rf, "rules_feat"):
        setattr(M, "rules_feat", getattr(rf, "rules_feat"))
    m.rules_feat = getattr(rf, "rules_feat")
    sys.modules[missing_mod] = m
    return True

def unwrap_estimator(obj):
    if hasattr(obj, "predict"): return obj, None
    if isinstance(obj, dict):
        for k in ("pipe","pipeline","estimator","clf","model"):
            if k in obj and hasattr(obj[k], "predict"): return obj[k], obj
    return obj, None

def as_csr(x):
    if sp.issparse(x): return x.tocsr()
    if isinstance(x, np.ndarray): return sp.csr_matrix(x if x.ndim==2 else x.reshape(1,-1))
    raise TypeError(f"non-numeric branch output: {type(x).__name__}")

def feature_dims(pre):
    dims={}
    XS=["報價與交期","技術支援","發票抬頭","退訂連結"]
    if hasattr(pre, "transformer_list"):
        for name,tr in pre.transformer_list:
            try: dims[name]=as_csr(tr.transform(XS)).shape[1]
            except Exception as e: dims[name]=f"ERR:{type(e).__name__}"
    return dims

def expected_dim_from_clf(clf):
    if hasattr(clf, "n_features_in_"): return int(clf.n_features_in_)
    if hasattr(clf, "base_estimator") and hasattr(clf.base_estimator, "n_features_in_"):
        return int(clf.base_estimator.n_features_in_)
    return None

def align_by_zeropad(pipe):
    # 取得 pre/union
    steps = dict(getattr(pipe,"steps",[]))
    pre = steps.get("features") or steps.get("pre") or steps.get("union")
    if pre is None: 
        return pipe, {"note":"no_pre_union"}
    dims = feature_dims(pre)
    num_sum = sum(v for v in dims.values() if isinstance(v,int))
    clf = pipe if not hasattr(pipe,"steps") else list(steps.values())[-1]
    expected = expected_dim_from_clf(clf)
    delta = None if expected is None or not num_sum else (expected - num_sum)
    changed=False
    if delta and hasattr(pre,"transformer_list"):
        # 優先找已存在且有 width 的分支
        for i,(name,tr) in enumerate(pre.transformer_list):
            if hasattr(tr,"width"):
                try:
                    old = int(getattr(tr,"width",1) or 1)
                    new = old + delta
                    setattr(tr,"width",int(new))
                    pre.transformer_list[i]=(name,tr)
                    changed=True
                    break
                except: pass
        if not changed:
            # 新增一個 pad_auto 分支
            from sma_tools.sk_zero_pad import ZeroPad
            pre.transformer_list.append(("pad_auto", ZeroPad(width=int(delta))))
            changed=True
    return pipe, dict(expected=expected, branch_dims=dims, sum_before=num_sum, delta=delta, changed=changed)

def main():
    # 0) env
    wjson("env.json", env_snapshot())

    # 1) 找 code_root & pkl
    code_root = find_code_root()
    if not code_root:
        print("[FATAL] 找不到 intent/intent 或 intent/", flush=True)
        sys.exit(2)
    print("[CODE_ROOT]", code_root, flush=True)
    pkl = find_pkl(code_root)
    if not pkl:
        print("[FATAL] 找不到 intent/artifacts/*.pkl", flush=True)
        sys.exit(3)
    print("[PKL]", pkl, flush=True)

    # 2) 複製 rules_feat 到 vendor，讓之後 alias 可以指過來
    copied = copy_rules_feat(code_root)
    if copied: print("[rules_feat] copied ->", copied, flush=True)

    # 3) 載入 old model（必要時補 alias）
    load_report = {"path": str(pkl), "ok": False, "err": None, "alias": None}
    try:
        obj = joblib.load(pkl)
    except ModuleNotFoundError as e:
        missing = e.name
        load_report["alias"] = missing
        ok = bind_rules_feat_alias(missing)
        print("[ALIAS]", missing, "-> vendor.rules_features.rules_feat", "ok=",ok, flush=True)
        obj = joblib.load(pkl)  # retry
    except Exception as e:
        load_report["err"] = f"{type(e).__name__}: {e}"
        (LOGDIR/"last_trace.txt").write_text(traceback.format_exc(), encoding="utf-8")
        wjson("pkl_load_report.json", load_report)
        raise
    load_report["ok"] = True
    wjson("pkl_load_report.json", load_report)

    est, meta = unwrap_estimator(obj)
    if not hasattr(est,"predict"):
        print("[FATAL] 不是可推論的 estimator", flush=True); sys.exit(4)

    # 4) 對齊（ZeroPad）
    aligned, info = align_by_zeropad(est)
    wjson("diagnostics.json", info)

    # 5) 存檔
    OUT = Path("artifacts/intent_pipeline_aligned.pkl")
    try:
        joblib.dump(aligned, OUT)
        print("[SAVED]", OUT, flush=True)
    except Exception as e:
        (LOGDIR/"last_trace.txt").write_text(traceback.format_exc(), encoding="utf-8")
        print("[SAVE_FAIL]", type(e).__name__, e, flush=True)
        raise

    # 6) 煙囪測
    TO_ZH = {"biz_quote":"報價","tech_support":"技術支援","complaint":"投訴","policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"}
    S = ["您好，想詢問報價與交期","請協助開立三聯發票抬頭","需要技術支援協助，附件連不上","退訂連結在此"]
    try:
        pred = aligned.predict(S)
        out = {"samples": S, "pred": [str(x) for x in pred], "pred_zh": [TO_ZH.get(str(x), str(x)) for x in pred]}
        print("\n".join(f"    {s} -> {y} / {TO_ZH.get(str(y), str(y))}" for s,y in zip(S,pred)), flush=True)
        wjson("sample_pred.json", out)
    except Exception:
        (LOGDIR/"last_trace.txt").write_text(traceback.format_exc(), encoding="utf-8")

    print("[DONE] see:", LOGDIR, flush=True)

if __name__=="__main__":
    try:
        main()
    except Exception:
        (LOGDIR/"last_trace.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise

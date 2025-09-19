from __future__ import annotations
import os, sys, json, time, traceback, types, importlib, importlib.abc, importlib.machinery
from pathlib import Path
import joblib, numpy as np
from scipy import sparse as sp

ROOT = Path.cwd()
OUTDIR = Path(os.environ.get("INTENT_DEBUG_DIR", f"reports_auto/intent_debug/{time.strftime('%Y%m%dT%H%M%S')}"))
OUTDIR.mkdir(parents=True, exist_ok=True)

def w(path, text, mode="w"):
    p = OUTDIR / path
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open(mode, encoding="utf-8") as f: f.write(text)
    return str(p)

def dump_json(name, obj):
    return w(name, json.dumps(obj, ensure_ascii=False, indent=2))

# --- 匯入監聽：記錄所有 import 失敗（根因常在這） ---
IMPORT_EVENTS = []
class LoggingFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        IMPORT_EVENTS.append({"event":"find", "name":fullname, "path":str(path)})
        return None
sys.meta_path.insert(0, LoggingFinder())

def env_snapshot():
    info = {
        "python": sys.version,
        "cwd": str(ROOT),
        "PYTHONPATH": os.environ.get("PYTHONPATH",""),
    }
    try:
        import numpy, scipy, sklearn
        info.update({
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
            "sklearn": sklearn.__version__,
            "joblib": joblib.__version__,
        })
    except Exception as e:
        info["lib_err"] = f"{type(e).__name__}: {e}"
    dump_json("env.json", info)

def list_candidates():
    intent_dir = ROOT / "intent"
    arts_dir   = ROOT / "artifacts"
    pats = [
        intent_dir / "artifacts" / "*.pkl",
        intent_dir / "*.pkl",
        arts_dir / "*.pkl",
        ROOT / "artifacts" / "**" / "*.pkl",
        ROOT / "intent" / "**" / "*.pkl",
    ]
    cands=[]
    for pat in pats:
        cands += list(Path(ROOT).glob(str(pat.relative_to(ROOT))))
    # 去重：按距離 intent 目錄近優先
    seen=set(); out=[]
    for p in cands:
        k=str(p.resolve())
        if k in seen: continue
        seen.add(k); out.append(p)
    dump_json("pkl_candidates.json", [str(p) for p in out])
    return out

def to_csr(X):
    if sp.issparse(X): return X.tocsr()
    if hasattr(X, "toarray"): X = X.toarray()
    if isinstance(X, np.ndarray): return sp.csr_matrix(X if X.ndim==2 else X.reshape(1,-1))
    if isinstance(X, list): return sp.csr_matrix((len(X), 1))
    raise TypeError(f"unsupported branch output {type(X)}")

def branch_dims(pipe, samples):
    dims={}
    try:
        steps=dict(pipe.steps)
        feats=steps.get("features") or steps.get("pre") or steps.get("feats")
        if hasattr(feats, "transformer_list"):
            for n,tr in feats.transformer_list:
                try:
                    Y=to_csr(tr.transform(samples))
                    dims[str(n)]=int(Y.shape[1])
                except Exception as e:
                    dims[str(n)]=f"ERR:{type(e).__name__}:{e}"
    except Exception as e:
        dims["__error__"]=f"{type(e).__name__}:{e}"
    return dims

def expected_dim(final_est):
    # 支援 LinearSVC / LogisticRegression / CalibratedClassifierCV(estimator=…)
    from sklearn.calibration import CalibratedClassifierCV
    est = final_est
    if isinstance(est, CalibratedClassifierCV):
        est = est.estimator
    if hasattr(est, "coef_"): return int(est.coef_.shape[1])
    if hasattr(est, "n_features_in_"): return int(est.n_features_in_)
    return None

def guess_root_cause(load_err:str|None, pred_err:str|None, dims:dict, need:int|None):
    if load_err and "No module named 'sma_tools" in load_err:
        return {"code":"missing_sma_tools", "msg":"缺少 sma_tools（當年自訂 transformer）"}
    if load_err and "ZeroPad" in load_err and "attribute" in load_err:
        return {"code":"zeropad_state_missing", "msg":"ZeroPad 反序列化缺屬性（例如 width）"}
    if pred_err and "features" in pred_err and "expect" in pred_err:
        return {"code":"n_features_mismatch", "msg":"特徵總欄數與分類器期望不一致"}
    if dims and any(str(v).startswith("ERR:") for v in dims.values()):
        return {"code":"branch_transform_error", "msg":"某分支 transform 失敗，詳見 dims"}
    return {"code":"unknown", "msg":"請檢查 run.log / diagnostics.json 詳細堆疊"}

def main():
    env_snapshot()

    # 列出 zip/intent 內容摘要（方便你對照）
    from pathlib import Path
    tree = []
    for p in Path("intent").rglob("*"):
        if p.is_file(): tree.append(str(p))
    dump_json("intent_tree.json", tree[:2000])  # 前 2000 條

    # 嘗試逐一載入
    cands = list_candidates()
    load_report=[]
    chosen=None; pipe=None; load_err=None
    for p in cands:
        rec={"path":str(p), "ok":False, "error":None}
        try:
            obj = joblib.load(p)
            # 轉 pipeline（如果是 dict）
            if isinstance(obj, dict):
                from sklearn.pipeline import Pipeline, FeatureUnion
                feats = obj.get("features") or obj.get("pre") or obj.get("feats")
                last  = obj.get("clf") or obj.get("cal") or obj.get("estimator") or obj.get("model")
                if isinstance(feats, FeatureUnion) and last is not None:
                    obj = Pipeline([("features", feats), ("clf", last)])
            pipe = obj if hasattr(obj, "predict") else None
            rec["ok"]=bool(pipe)
            if pipe:
                chosen=str(p); load_report.append(rec); break
            else:
                rec["error"]="object has no predict()"
        except Exception as e:
            rec["error"]=f"{type(e).__name__}: {e}"
        load_report.append(rec)

    dump_json("pkl_load_report.json", load_report)
    if not pipe:
        load_err = load_report[-1]["error"] if load_report else "No candidates"
        w("last_trace.txt", load_err)
        dump_json("root_cause.json", guess_root_cause(load_err, None, {}, None))
        print("[FATAL] 無法載入任何 PKL，詳見 pkl_load_report.json / last_trace.txt")
        return

    # 成功載入：做分支維度 / 期望維度 / 逐句推論
    steps = dict(pipe.steps) if hasattr(pipe, "steps") else {}
    final = steps.get("cal") or steps.get("clf") or pipe
    need  = expected_dim(final)
    samples = ["您好，想詢問報價與交期","請協助開立三聯發票抬頭","需要技術支援協助，附件連不上","退訂連結在此"]
    dims = branch_dims(pipe, samples)
    summary = {"pkl":chosen, "expected_dim":need, "branch_dims":dims}
    dump_json("diagnostics.json", summary)

    pred_err=None
    try:
        ys = pipe.predict(samples)
        dump_json("sample_pred.json", {"samples":samples, "pred":list(map(str,ys))})
    except Exception as e:
        pred_err = f"{type(e).__name__}: {e}"
        w("last_trace.txt", traceback.format_exc())

    dump_json("root_cause.json", guess_root_cause(None, pred_err, dims, need))
    print("[DONE] 診斷完成；請查看：", OUTDIR)

if __name__ == "__main__":
    main()

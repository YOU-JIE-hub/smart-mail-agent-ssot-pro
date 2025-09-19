#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, json, pathlib, re, collections, traceback
import numpy as np, joblib

root = pathlib.Path(".")

# ----------------------------
# 1) 安全 shims（修你剛遇到的 scipy.sparse object dtype）
#    - rules_feat -> list[dict]（給 DictVectorizer）
#    - prio_feat / bias_feat -> np.zeros((n, 1), float64)（給數值支路）
# ----------------------------
def _ensure_list(X):
    try:
        import numpy as _np
        if isinstance(X, _np.ndarray): X = X.tolist()
    except Exception: pass
    if isinstance(X, (str, bytes)): return [X]
    try: iter(X); return list(X)
    except Exception: return [X]

def rules_feat(X, *a, **k):
    return [ {} for _ in _ensure_list(X) ]

def _zeros_feat(X, *a, **k):
    n = len(_ensure_list(X))
    return np.zeros((n, 1), dtype=float)  # 確保 downstream dtype 不是 object

# 提前把名稱綁上 __main__ 給 pickle 找
globals().update({
    "rules_feat": rules_feat,
    "prio_feat": _zeros_feat,
    "bias_feat": _zeros_feat,
})

def _load_with_auto_shim(pkl_path, max_retry=12):
    last=None
    for _ in range(max_retry):
        try:
            return joblib.load(pkl_path)
        except AttributeError as e:
            # 自動補任何訓練期掛在 __main__ 的函式
            m = re.search(r"Can't get attribute '([^']+)'", str(e))
            if not m: raise
            missing = m.group(1)
            if missing not in globals():
                # 預設用 zeros 支路（避免 object dtype）
                globals()[missing] = _zeros_feat
                last = str(e); continue
            raise
    raise RuntimeError(f"too many shim retries; last={last}")

# ----------------------------
# 2) 挑出真正可預測的估計器（有 predict）
# ----------------------------
def _get_estimator(obj):
    if hasattr(obj, "predict"): return obj
    if isinstance(obj, dict):
        for k in ["pipe","pipeline","model","clf","estimator","best_estimator_"]:
            if k in obj and hasattr(obj[k], "predict"):
                return obj[k]
    return None

def _get_classes(est):
    # 盡量撈 classes_；Pipeline 走到末端或反查步驟
    if hasattr(est, "classes_"): return est.classes_
    if hasattr(est, "steps"):
        for _, step in reversed(est.steps):
            if hasattr(step, "classes_"): return step.classes_
    return None

# ----------------------------
# 3) 讀 names / thresholds / rules
# ----------------------------
def _load_names(path="artifacts_prod/intent_names.json"):
    p = root / path
    if not p.exists(): return []
    try:
        obj = json.load(open(p,"r",encoding="utf-8"))
        if isinstance(obj, list): names=obj
        elif isinstance(obj, dict) and isinstance(obj.get("names"), list): names=obj["names"]
        elif isinstance(obj, dict): names=list(obj.keys())
        else: names=[]
        return [str(x) for x in names]
    except Exception:
        return []

def _load_json(path):
    p = root / path
    if not p.exists(): return None
    try:
        return json.load(open(p, "r", encoding="utf-8"))
    except Exception:
        return None

# ----------------------------
# 4) 資料嗅探 & 選 test/val（避開 spam/ham）
# ----------------------------
def _sniff(path, k=300):
    want_fields = ["intent","label","category","y"]
    spam_words  = {"spam","ham","phish"}
    names=set(); ids=set(); Xn=0
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i>=k: break
            line=line.strip()
            if not line: continue
            Xn += 1
            try: obj=json.loads(line)
            except Exception: continue
            for fld in want_fields:
                v=obj.get(fld)
                if isinstance(v,str): names.add(v)
                if isinstance(v,(int,np.integer,str)) and str(v).isdigit(): ids.add(int(v))
    spam_like = (len(names)>0) and (names <= spam_words)
    return {"spam_like": spam_like, "names_count": len(names), "ids_count": len(ids), "n": Xn}

def _choose_dataset():
    tests = [
        "data/intent/test_labeled.fixed.jsonl",
        "data/intent/test.jsonl",
        "data/intent/test_labeled.jsonl",
        "data/prod_merged/test.jsonl",
        "reports_auto/intent/test.jsonl",
    ]
    vals = [
        "data/intent/val.jsonl",
        "data/intent_eval/dataset.cleaned.jsonl",
        "reports_auto/intent/val.jsonl",
    ]
    tests = [str(root/p) for p in tests if (root/p).exists()]
    vals  = [str(root/p) for p in vals  if (root/p).exists()]
    if not tests or not vals:
        raise SystemExit("[FATAL] 找不到 test/val 候選檔")

    def _best(cands):
        scored=[]
        for p in cands:
            s=_sniff(p)
            print(f"[Sniff] {p} | spam_like={s['spam_like']} names={s['names_count']} ids={s['ids_count']} n={s['n']}")
            # 避開 spam_like；名稱多者優先；id 少者優先（代表不是編號標註）
            scored.append((0 if s["spam_like"] else 1, s["names_count"], -s["ids_count"], p))
        scored.sort(reverse=True)
        return scored[0][-1]
    return _best(tests), _best(vals)

def _read_jsonl(path):
    X, gname = [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: obj=json.loads(line)
            except Exception:
                X.append(line); gname.append(None); continue
            txt=(obj.get("text") or obj.get("content") or obj.get("body") or obj.get("message") or obj.get("q") or "")
            X.append("" if txt is None else str(txt))
            lab=(obj.get("intent") or obj.get("label") or obj.get("category"))
            gname.append(None if lab is None else str(lab))
    return X, gname

# ----------------------------
# 5) Pipeline 深度探針（逐支路 transform，抓 dtype/shape）
# ----------------------------
def _is_sparse(x):
    try:
        import scipy.sparse as sp
        return sp.issparse(x)
    except Exception:
        return False

def _shape_dtype_info(x):
    info={"type": type(x).__name__}
    try:
        if _is_sparse(x):
            info["sparse"]=True
            info["shape"]=tuple(x.shape)
            info["dtype"]=str(x.dtype)
        elif hasattr(x, "shape"):
            info["shape"]=tuple(x.shape)
            info["dtype"]=str(getattr(x, "dtype", None))
        elif isinstance(x, (list, tuple)):
            info["len"]=len(x)
            info["elem_type"]=type(x[0]).__name__ if x else None
        else:
            info["repr"]=repr(x)[:80]
    except Exception as e:
        info["err"]=f"{type(e).__name__}: {e}"
    return info

def _probe_feature_union(fu, X):
    results=[]
    for name, tr in fu.transformer_list:
        rec={"name":name, "class":type(tr).__name__}
        try:
            out = tr.transform(X)
            rec.update(_shape_dtype_info(out))
        except Exception as e:
            rec["error"]=f"{type(e).__name__}: {e}"
            rec["traceback"]=traceback.format_exc(limit=1)
        results.append(rec)
    # Union 輸出
    try:
        out_all = fu.transform(X)
        results.append({"name":"<union_out>", **_shape_dtype_info(out_all)})
    except Exception as e:
        results.append({"name":"<union_out>", "error":f"{type(e).__name__}: {e}"})
    return results

def _introspect_pipeline(est, Xsamp):
    info=[]
    obj=est
    # 支援 Pipeline 串起來的 FeatureUnion / ColumnTransformer
    try:
        from sklearn.pipeline import Pipeline, FeatureUnion
        from sklearn.compose import ColumnTransformer
    except Exception:
        Pipeline=FeatureUnion=ColumnTransformer=type("N",(),{}) # dummy

    if hasattr(obj, "steps"):
        X=Xsamp
        for name, step in obj.steps:
            rec={"step":name, "class":type(step).__name__}
            if isinstance(step, FeatureUnion):
                rec["feature_union"] = _probe_feature_union(step, X)
                # union 輸出當下一步輸入
                try:
                    X = step.transform(X)
                    rec["out"]=_shape_dtype_info(X)
                except Exception as e:
                    rec["error"]=f"{type(e).__name__}: {e}"
                    info.append(rec)
                    break
            elif hasattr(step, "transform"):
                try:
                    X = step.transform(X)
                    rec["out"]=_shape_dtype_info(X)
                except Exception as e:
                    rec["error"]=f"{type(e).__name__}: {e}"
                    info.append(rec)
                    break
            else:
                rec["note"]="no transform; probably final estimator"
            info.append(rec)
    else:
        info.append({"note":"not a sklearn Pipeline"})
    return info

# ----------------------------
# 6) 評估與輸出
# ----------------------------
def _names_from_pred(est, X, id2name):
    y = est.predict(X)
    out=[]
    for v in y:
        if isinstance(v, (str,)):
            out.append(v)
        elif isinstance(v, (int, np.integer)) and int(v) in id2name:
            out.append(id2name[int(v)])
        else:
            out.append(str(v))
    return out

def _acc(pred, gold):
    ok=0; tot=0
    for p,g in zip(pred, gold):
        if g is None: continue
        tot += 1; ok += int(p==g)
    return ok, tot, (ok/tot if tot else 0.0)

def _topk(vals, k=10):
    c=collections.Counter(v for v in vals if v is not None)
    return c.most_common(k)

def _find_intent_model():
    cands=[]
    for r in [root/"artifacts", root/"artifacts_prod"]:
        if not r.exists(): continue
        for p in r.rglob("*.pkl"):
            try:
                obj=_load_with_auto_shim(p)
                est=_get_estimator(obj)
                if not est: continue
                cls=_get_classes(est)
                if cls is None: continue
                cls_list = list(cls) if not hasattr(cls,"tolist") else cls.tolist()
                n=len(cls_list)
                set_str=set(map(str, cls_list))
                is_spam = (set_str <= {"spam","ham"}) or (n<=2)
                cands.append({"path":str(p), "n":n, "is_spam":is_spam, "est":est})
            except Exception:
                continue
    cands=[c for c in cands if not c["is_spam"]]
    if not cands: raise SystemExit("[FATAL] 找不到可用意圖模型（只有 spam/二分類或無 classes_）")
    cands.sort(key=lambda x:(-x["n"], x["path"]))
    best=cands[0]
    print(f"[MODEL] {best['path']} | classes={best['n']}")
    return best["est"], best["path"]

def main():
    names = _load_names()
    id2name = {i:n for i,n in enumerate(names)} if names else {}
    thr = _load_json("reports_auto/intent_thresholds.json")
    rules = _load_json("artifacts_prod/intent_rules_calib.json")

    est, mpath = _find_intent_model()

    test_path, val_path = _choose_dataset()
    print(f"[DATA] test={test_path}")
    print(f"[DATA] val ={val_path}")

    Xt, gt = _read_jsonl(test_path)
    Xv, gv = _read_jsonl(val_path)

    # Pipeline 深度探針（用少量樣本）
    Xsamp = Xt[:8] if Xt else [""]
    pipe_probe = _introspect_pipeline(est, Xsamp)

    # 真正預測（名稱空間）
    pt = _names_from_pred(est, Xt, id2name)
    pv = _names_from_pred(est, Xv, id2name)

    okt,tott,acct = _acc(pt, gt)
    okv,totv,accv = _acc(pv, gv)

    # mismatch 範例
    mismT=[]; mismV=[]
    for i,(p,g) in enumerate(zip(pt,gt)):
        if g is not None and p!=g:
            mismT.append({"i":i,"pred":p,"gold":g})
        if len(mismT)>=5: break
    for i,(p,g) in enumerate(zip(pv,gv)):
        if g is not None and p!=g:
            mismV.append({"i":i,"pred":p,"gold":g})
        if len(mismV)>=5: break

    rep={
        "env": {
            "python": sys.version.split()[0],
        },
        "names": {
            "len": len(names),
            "head": names[:10],
        },
        "thresholds_keys": list(thr.keys()) if isinstance(thr, dict) else None,
        "rules_loaded": isinstance(rules, dict),
        "model": {
            "path": mpath,
            "classes_len": len(_get_classes(est)) if _get_classes(est) is not None else None,
            "pipeline_probe": pipe_probe,
        },
        "data": {
            "test": test_path,
            "val": val_path
        },
        "eval": {
            "test": {"n": len(Xt), "labeled": tott, "acc": acct, "pred_top": _topk(pt), "mismatch_sample": mismT},
            "val":  {"n": len(Xv), "labeled": totv, "acc": accv, "pred_top": _topk(pv), "mismatch_sample": mismV},
        }
    }
    out = root/"reports_auto"/"debug"
    out.mkdir(parents=True, exist_ok=True)
    with open(out/"intent_diag.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    # 終端可讀摘要
    print("\n===== SUMMARY =====")
    print(f"names_len={rep['names']['len']}  model_classes={rep['model']['classes_len']}")
    print(f"TEST: n={rep['eval']['test']['n']} labeled={rep['eval']['test']['labeled']} acc={rep['eval']['test']['acc']:.4f}  top={rep['eval']['test']['pred_top'][:3]}")
    print(f"VAL : n={rep['eval']['val']['n']}  labeled={rep['eval']['val']['labeled']}  acc={rep['eval']['val']['acc']:.4f}  top={rep['eval']['val']['pred_top'][:3]}")
    print("PIPELINE PROBE (first union/step dtypes):")
    for rec in rep["model"]["pipeline_probe"][:6]:
        print(" -", rec.get("step") or rec.get("note"), rec.get("class"), rec.get("out", rec.get("error")))

if __name__ == "__main__":
    main()

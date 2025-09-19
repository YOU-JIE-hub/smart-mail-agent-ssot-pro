#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, json, pathlib, re, collections
import numpy as np, joblib

root = pathlib.Path(".")

# ---- shims：訓練期的 __main__ 特徵 ----
def _ensure_list(X):
    try:
        import numpy as _np
        if isinstance(X, _np.ndarray): X = X.tolist()
    except Exception: pass
    if isinstance(X, (str, bytes)): return [X]
    try: iter(X); return list(X)
    except Exception: return [X]

def rules_feat(X,*a,**k): return [ {} for _ in _ensure_list(X) ]  # for DictVectorizer
def _zeros_feat(X,*a,**k): return np.zeros((len(_ensure_list(X)),1), dtype=float)
globals().update({"prio_feat":_zeros_feat, "bias_feat":_zeros_feat})

# ---- 讀設定 ----
def load_json(path):
    p=root/path
    if not p.exists(): return None
    try: return json.load(open(p,"r",encoding="utf-8"))
    except Exception: return None

def load_names(path="artifacts_prod/intent_names.json"):
    obj=load_json(path)
    if obj is None: return []
    if isinstance(obj,list): return [str(x) for x in obj]
    if isinstance(obj,dict) and isinstance(obj.get("names"),list): return [str(x) for x in obj["names"]]
    if isinstance(obj,dict): return [str(k) for k in obj.keys()]
    return []

# ---- 安全載入 ----
def load_with_auto_shim(pkl, max_retry=12):
    last=None
    for _ in range(max_retry):
        try:
            return joblib.load(pkl)
        except AttributeError as e:
            m=re.search(r"Can't get attribute '([^']+)'", str(e))
            if not m: raise
            missing=m.group(1)
            if missing not in globals():
                globals()[missing]=_zeros_feat
                last=str(e); continue
            raise
    raise RuntimeError(f"too many shim retries; last={last}")

def get_estimator(obj):
    if hasattr(obj,"predict"): return obj
    if isinstance(obj,dict):
        for k in ("pipe","pipeline","model","clf","estimator","best_estimator_"):
            if k in obj and hasattr(obj[k],"predict"): return obj[k]
    return None

def get_classes(est):
    if hasattr(est,"classes_"): return est.classes_
    if hasattr(est,"steps"):
        for _,step in reversed(est.steps):
            if hasattr(step,"classes_"): return step.classes_
    return None

# ---- sniff / 讀資料 ----
def sniff(path,k=300):
    want=["intent","label","category","y"]
    spam={"spam","ham","phish"}
    names=set(); ids=set(); n=0
    with open(path,"r",encoding="utf-8") as f:
        for i,line in enumerate(f):
            if i>=k: break
            line=line.strip()
            if not line: continue
            n+=1
            try: obj=json.loads(line)
            except Exception: continue
            for fld in want:
                v=obj.get(fld)
                if isinstance(v,str): names.add(v)
                if isinstance(v,(int,np.integer,str)) and str(v).isdigit(): ids.add(int(v))
    return {"spam_like": (len(names)>0 and names<=spam), "names_count":len(names), "ids_count":len(ids), "n":n}

def choose_dataset():
    tests=[
        "data/intent/test_labeled.fixed.jsonl",
        "data/intent/test.jsonl",
        "data/intent/test_labeled.jsonl",
        "data/prod_merged/test.jsonl",
        "reports_auto/intent/test.jsonl",
    ]
    vals=[
        "data/intent/val.jsonl",
        "data/intent_eval/dataset.cleaned.jsonl",
        "reports_auto/intent/val.jsonl",
    ]
    tests=[str(root/p) for p in tests if (root/p).exists()]
    vals =[str(root/p) for p in vals  if (root/p).exists()]
    if not tests or not vals:
        raise SystemExit("[FATAL] 找不到 test/val 候選檔")
    def pick(cands):
        scored=[]
        for p in cands:
            s=sniff(p)
            print(f"[Sniff] {p} | spam_like={s['spam_like']} names={s['names_count']} ids={s['ids_count']} n={s['n']}")
            scored.append((0 if s["spam_like"] else 1, s["names_count"], -s["ids_count"], p))
        scored.sort(reverse=True)
        return scored[0][-1]
    return pick(tests), pick(vals)

def read_jsonl(path):
    X, gname = [], []
    with open(path,"r",encoding="utf-8") as f:
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

# ---- pipeline 探針與修補 ----
def _is_sparse(x):
    try:
        import scipy.sparse as sp
        return sp.issparse(x)
    except Exception:
        return False

_NUMERIC_KINDS=set("biufc")  # bool, int, unsigned, float, complex
def _is_numeric_dtype(dtype):
    try:
        k=np.dtype(dtype).kind
        return k in _NUMERIC_KINDS
    except Exception:
        return False

def _ok_output(out):
    # 合法：稀疏且 dtype 非 object；或 ndarray 且數值 dtype
    if _is_sparse(out):
        return _is_numeric_dtype(getattr(out,"dtype",None))
    if isinstance(out, np.ndarray):
        return _is_numeric_dtype(out.dtype)
    # 其他（list/tuple/dict/None/str…）一律視為不合法
    return False

def _n_cols_of(out):
    try:
        sh=getattr(out,"shape",None)
        if sh is not None:
            if len(sh)==2: return int(sh[1])
            if len(sh)==1: return 1
    except Exception:
        pass
    return 1

def _estimate_cols(tr, X):
    try:
        o=tr.transform(X[:1])
        return max(1,_n_cols_of(o))
    except Exception:
        return 1

from sklearn.base import BaseEstimator, TransformerMixin
class ConstantZeros(BaseEstimator, TransformerMixin):
    def __init__(self, n_cols=1, dtype=float): self.n_cols=int(n_cols); self.dtype=dtype
    def fit(self, X, y=None): return self
    def transform(self, X):
        import scipy.sparse as sp
        n=len(_ensure_list(X))
        return sp.csr_matrix((n, self.n_cols), dtype=self.dtype)

def probe_and_patch_pipeline(est, Xsamp, log):
    from sklearn.pipeline import Pipeline, FeatureUnion
    records=[]
    if not hasattr(est,"steps"):
        print("[WARN] 不是 sklearn Pipeline；跳過探針", file=log)
        return records, est

    for idx,(name,step) in enumerate(list(est.steps)):
        rec={"step":name, "class":type(step).__name__}
        if isinstance(step, FeatureUnion):
            new_list=[]
            fu_recs=[]
            for br_name, tr in step.transformer_list:
                r={"name":br_name, "class":type(tr).__name__}
                try:
                    out=tr.transform(Xsamp)
                    ok=_ok_output(out)
                    n_cols=_n_cols_of(out)
                    if not ok:
                        n_cols = max(n_cols, _estimate_cols(tr, Xsamp))
                        tr = ConstantZeros(n_cols=n_cols, dtype=float)
                        r["patched"]=f"ConstantZeros({n_cols})"
                    else:
                        r["dtype"]=str(getattr(out,"dtype",None))
                        r["shape"]=tuple(getattr(out,"shape", (len(out),1)))
                except Exception as e:
                    n_cols=_estimate_cols(tr, Xsamp)
                    tr = ConstantZeros(n_cols=n_cols, dtype=float)
                    r["error"]=f"{type(e).__name__}: {e}"
                    r["patched"]=f"ConstantZeros({n_cols})"
                fu_recs.append(r)
                new_list.append((br_name, tr))
            step.transformer_list = new_list
            rec["feature_union"]=fu_recs
            try:
                out_all=step.transform(Xsamp)
                rec["out_dtype"]=str(getattr(out_all,"dtype",None))
                rec["out_shape"]=tuple(getattr(out_all,"shape",(0,0)))
            except Exception as e:
                rec["error"]=f"{type(e).__name__}: {e}"
        elif hasattr(step,"transform"):
            try:
                out=step.transform(Xsamp)
                if not _ok_output(out):
                    # 單變換器直接打零（用估出來的寬度）
                    n_cols=_estimate_cols(step, Xsamp)
                    zero=ConstantZeros(n_cols=n_cols, dtype=float)
                    est.steps[idx]=(name, zero)
                    rec["patched"]=f"ConstantZeros({n_cols})"
                else:
                    rec["out_dtype"]=str(getattr(out,"dtype",None))
                    rec["out_shape"]=tuple(getattr(out,"shape",(0,0)))
            except Exception as e:
                n_cols=_estimate_cols(step, Xsamp)
                zero=ConstantZeros(n_cols=n_cols, dtype=float)
                est.steps[idx]=(name, zero)
                rec["error"]=f"{type(e).__name__}: {e}"
                rec["patched"]=f"ConstantZeros({n_cols})"
        else:
            rec["note"]="no transform; probably final estimator"
        records.append(rec)

    # 簡短輸出
    print("PIPELINE PROBE:", file=log)
    for rec in records:
        line=f" - {rec.get('step')} {rec.get('class')} "
        if "feature_union" in rec:
            line += f"union_out={rec.get('out_shape')} dtype={rec.get('out_dtype')}"
        elif "out_shape" in rec:
            line += f"out={rec.get('out_shape')} dtype={rec.get('out_dtype')}"
        if "patched" in rec: line += f"  PATCHED={rec['patched']}"
        if "error" in rec: line += f"  ERR={rec['error']}"
        print(line, file=log)
        if "feature_union" in rec:
            for r in rec["feature_union"]:
                desc=r.get("patched") or (r.get("dtype") and f"dtype={r['dtype']}") or r.get("error") or "ok"
                print(f"    * {r['name']} {r['class']} -> {desc}", file=log)
    return records, est

# ---- 評估 ----
def names_from_pred(est, X, id2name):
    y=est.predict(X)
    out=[]
    for v in y:
        if isinstance(v,str): out.append(v); continue
        if isinstance(v,(int,np.integer)) and int(v) in id2name: out.append(id2name[int(v)]); continue
        out.append(str(v))
    return out

def acc_tuple(pred,gold):
    ok=0; tot=0
    for p,g in zip(pred,gold):
        if g is None: continue
        tot+=1; ok+= int(p==g)
    return ok, tot, (ok/tot if tot else 0.0)

def topk(vals,k=10):
    c=collections.Counter(v for v in vals if v is not None)
    return c.most_common(k)

# ---- 找非 spam 的意圖模型 ----
def find_intent_model():
    cands=[]
    for r in [root/"artifacts", root/"artifacts_prod"]:
        if not r.exists(): continue
        for p in r.rglob("*.pkl"):
            try:
                obj=load_with_auto_shim(p)
                est=get_estimator(obj)
                if not est: continue
                cls=get_classes(est)
                if cls is None: continue
                cls_list=list(cls) if not hasattr(cls,"tolist") else cls.tolist()
                n=len(cls_list); set_str=set(map(str,cls_list))
                is_spam=(set_str<= {"spam","ham"}) or (n<=2)
                cands.append({"path":str(p),"n":n,"is_spam":is_spam,"est":est})
            except Exception:
                continue
    cands=[c for c in cands if not c["is_spam"]]
    if not cands: raise SystemExit("[FATAL] 找不到可用意圖模型（只有 spam/二分類或無 classes_）")
    cands.sort(key=lambda x:(-x["n"], x["path"]))
    best=cands[0]
    print(f"[MODEL] {best['path']} | classes={best['n']}")
    return best["est"], best["path"]

def main():
    names=load_names(); id2name={i:n for i,n in enumerate(names)} if names else {}
    thr=load_json("reports_auto/intent_thresholds.json")
    rules=load_json("artifacts_prod/intent_rules_calib.json")

    est, mpath = find_intent_model()
    test_path, val_path = choose_dataset()
    print(f"[DATA] test={test_path}")
    print(f"[DATA] val ={val_path}")

    Xt, gt = read_jsonl(test_path)
    Xv, gv = read_jsonl(val_path)
    Xsamp = Xt[:8] if Xt else [""]

    probe_rec, est = probe_and_patch_pipeline(est, Xsamp, log=sys.stdout)

    pt = names_from_pred(est, Xt, id2name)
    pv = names_from_pred(est, Xv, id2name)

    okt,tott,acct = acc_tuple(pt,gt)
    okv,totv,accv = acc_tuple(pv,gv)

    rep={
        "env":{"python":sys.version.split()[0]},
        "names":{"len":len(names), "head":names[:10]},
        "thresholds_keys": list(thr.keys()) if isinstance(thr,dict) else None,
        "rules_loaded": isinstance(rules,dict),
        "model":{"path":mpath, "classes_len": (len(get_classes(est)) if get_classes(est) is not None else None), "probe":probe_rec},
        "data":{"test":test_path,"val":val_path},
        "eval":{
            "test":{"n":len(Xt),"labeled":tott,"acc":acct,"pred_top":topk(pt),"mismatch_sample":[{"i":i,"pred":p,"gold":g} for i,(p,g) in enumerate(zip(pt,gt)) if g is not None and p!=g][:5]},
            "val" :{"n":len(Xv),"labeled":totv,"acc":accv,"pred_top":topk(pv),"mismatch_sample":[{"i":i,"pred":p,"gold":g} for i,(p,g) in enumerate(zip(pv,gv)) if g is not None and p!=g][:5]},
        }
    }
    out = root/"reports_auto"/"debug"
    out.mkdir(parents=True, exist_ok=True)
    with open(out/"intent_diag.json","w",encoding="utf-8") as f:
        json.dump(rep,f,ensure_ascii=False,indent=2)

    print("\n===== SUMMARY =====")
    print(f"names_len={rep['names']['len']}  model_classes={rep['model']['classes_len']}")
    print(f"TEST: n={rep['eval']['test']['n']} labeled={rep['eval']['test']['labeled']} acc={rep['eval']['test']['acc']:.4f}  top={rep['eval']['test']['pred_top'][:3]}")
    print(f"VAL : n={rep['eval']['val']['n']}  labeled={rep['eval']['val']['labeled']}  acc={rep['eval']['val']['acc']:.4f}  top={rep['eval']['val']['pred_top'][:3]}")

if __name__=="__main__":
    main()

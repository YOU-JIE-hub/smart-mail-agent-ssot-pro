#!/usr/bin/env python
import pathlib, json, joblib, re, numpy as np, collections, sys

# -------- shims: 解 pickle 找不到 __main__.* 特徵函式 --------
def _ensure_list(X):
    try:
        import numpy as _np
        if isinstance(X, _np.ndarray): X = X.tolist()
    except Exception: pass
    if isinstance(X, (str, bytes)): return [X]
    try: iter(X); return list(X)
    except Exception: return [X]
def _shim_dict(X,*a,**k): return [ {} for _ in _ensure_list(X) ]
for _n in ["rules_feat","prio_feat","bias_feat"]:
    globals()[_n]=_shim_dict

def load_with_shim(p):
    last=None
    for _ in range(10):
        try: return joblib.load(p)
        except AttributeError as e:
            m=re.search(r"Can't get attribute '([^']+)'", str(e))
            if not m: raise
            nm=m.group(1)
            if nm not in globals():
                globals()[nm]=_shim_dict
                last=str(e); continue
            raise
    raise RuntimeError(f"too many shim retries; last={last}")

def get_estimator(obj):
    if hasattr(obj, "predict"): return obj
    if isinstance(obj, dict):
        for k in ["pipe","pipeline","model","clf","estimator","best_estimator_"]:
            if k in obj and hasattr(obj[k], "predict"): return obj[k]
    return None

def get_classes(est):
    if hasattr(est, "classes_"): return est.classes_
    if hasattr(est, "steps"):
        for _, step in reversed(est.steps):
            if hasattr(step, "classes_"): return step.classes_
    return None

def load_names(p):
    try:
        obj=json.load(open(p,"r",encoding="utf-8"))
        if isinstance(obj, list): names=obj
        elif isinstance(obj, dict) and isinstance(obj.get("names"), list): names=obj["names"]
        elif isinstance(obj, dict): names=list(obj.keys())
        else: names=[]
        return [str(x) for x in names]
    except Exception:
        return []

def score_model_path(p):
    try:
        obj=load_with_shim(p)
        est=get_estimator(obj)
        if not est: return None
        cls=get_classes(est)
        if cls is None: return None
        cls_list=list(cls) if not hasattr(cls, "tolist") else cls.tolist()
        n=len(cls_list)
        # 排除 spam 二分類
        set_str=set(map(str, cls_list))
        is_spam = set_str<= {"spam","ham"} or n<=2
        return {"path":str(p), "est":est, "n_classes":n, "is_spam":is_spam}
    except Exception:
        return None

def find_intent_model():
    roots=[pathlib.Path("artifacts"), pathlib.Path("artifacts_prod")]
    cands=[]
    for r in roots:
        if not r.exists(): continue
        for p in r.rglob("*.pkl"):
            s=score_model_path(p)
            if s: cands.append(s)
    cands=[c for c in cands if not c["is_spam"]]
    if not cands:
        raise SystemExit("[FATAL] 找不到可用意圖模型（只有 spam/二分類或無 classes_）")
    # 以類別數優先
    cands.sort(key=lambda x: (-x["n_classes"], x["path"]))
    best=cands[0]
    print(f"[MODEL] {best['path']} | classes={best['n_classes']}")
    return best["est"], best["path"]

def sniff_labels(path, k=200):
    want_fields = ["intent","label","category","y"]
    spam_words  = {"spam","ham","phish"}
    names=set(); ids=set(); spam_like=False
    X=[]
    with open(path, "r", encoding="utf-8") as f:
        for i,line in enumerate(f):
            if i>=k: break
            line=line.strip()
            if not line: continue
            try: obj=json.loads(line)
            except Exception: 
                X.append(line); continue
            txt=(obj.get("text") or obj.get("content") or obj.get("body") or obj.get("message") or obj.get("q") or "")
            X.append("" if txt is None else str(txt))
            for fld in want_fields:
                v=obj.get(fld)
                if isinstance(v,str): names.add(v)
                if isinstance(v,(int,np.integer,str)) and str(v).isdigit(): ids.add(int(v))
    if names and names <= spam_words: spam_like=True
    return {"spam_like":spam_like, "names":names, "ids":ids, "Xn":len(X)}

def choose_dataset():
    tests = [
        "data/intent/test.jsonl",
        "data/intent/test_labeled.fixed.jsonl",
        "data/intent/test_labeled.jsonl",
        "data/prod_merged/test.jsonl",
        "reports_auto/intent/test.jsonl",
    ]
    vals = [
        "data/intent/val.jsonl",
        "data/intent_eval/dataset.cleaned.jsonl",
        "reports_auto/intent/val.jsonl",
    ]
    pick=lambda L: [str(pathlib.Path(p)) for p in L if pathlib.Path(p).exists()]
    tests=pick(tests); vals=pick(vals)
    if not tests: raise SystemExit("[FATAL] 沒有可用 test 檔")
    if not vals:   raise SystemExit("[FATAL] 沒有可用 val 檔")

    def best(cands):
        scored=[]
        for p in cands:
            s=sniff_labels(p)
            scored.append((0 if s["spam_like"] else 1, len(s["names"]), -len(s["ids"]), p))
            print(f"[Sniff] {p} | spam_like={s['spam_like']} names={len(s['names'])} ids={len(s['ids'])} n={s['Xn']}")
        scored.sort(reverse=True)
        return scored[0][-1]

    return best(tests), best(vals)

def read_jsonl_for_eval(path):
    X, gname=[], []
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

def names_from_pred(est, X, id2name):
    y=est.predict(X)
    out=[]
    for v in y:
        if isinstance(v, (str,)):
            out.append(v)
        elif isinstance(v, (int, np.integer)) and v in id2name:
            out.append(id2name[int(v)])
        else:
            out.append(str(v))
    return out

def acc(pred, gold):
    ok=0; tot=0
    for p,g in zip(pred, gold):
        if g is None: continue
        tot += 1
        ok  += int(p==g)
    return ok, tot, (ok/tot if tot else 0.0)

def topk(vals, k=10):
    c=collections.Counter(v for v in vals if v is not None)
    return c.most_common(k)

def main():
    root=pathlib.Path(".")
    est, mpath = find_intent_model()

    names_path="artifacts_prod/intent_names.json"
    names=load_names(names_path)
    id2name={i:n for i,n in enumerate(names)} if names else {}

    test_path, val_path = choose_dataset()
    print(f"[DATA] test={test_path}")
    print(f"[DATA] val ={val_path}")

    Xt, gt = read_jsonl_for_eval(test_path)
    Xv, gv = read_jsonl_for_eval(val_path)

    pt = names_from_pred(est, Xt, id2name)
    pv = names_from_pred(est, Xv, id2name)

    okt, tott, acct = acc(pt, gt)
    okv, totv, accv = acc(pv, gv)

    # mismatches
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
        "model": mpath,
        "names_len": len(names),
        "test": {"n": len(Xt), "labeled": tott, "acc": acct, "pred_top": topk(pt), "mismatch_sample": mismT},
        "val":  {"n": len(Xv), "labeled": totv, "acc": accv, "pred_top": topk(pv), "mismatch_sample": mismV},
    }
    out=pathlib.Path("reports_auto/intent_eval_summary.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(rep, open(out,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(rep, ensure_ascii=False, indent=2))

if __name__=="__main__":
    main()

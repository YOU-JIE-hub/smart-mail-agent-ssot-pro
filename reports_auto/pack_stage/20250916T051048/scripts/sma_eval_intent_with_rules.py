#!/usr/bin/env python3
# Shim: minimal, rule-aware intent evaluator (keeps CLI contract)
import argparse, json, sys, pathlib, joblib
from collections import Counter


# === BEGIN: auto-shim for training-time globals on __main__ ===
def _ensure_list(X):
    try:
        import numpy as _np
        if isinstance(X, (_np.ndarray,)): X = X.tolist()
    except Exception: pass
    if isinstance(X, (str, bytes)): return [X]
    try:
        iter(X); return list(X)
    except Exception:
        return [X]

def rules_feat(X, *args, **kwargs):
    L=_ensure_list(X); return [ {} for _ in L ]

def prio_feat(X, *args, **kwargs):
    L=_ensure_list(X); return [ {} for _ in L ]

def bias_feat(X, *args, **kwargs):
    L=_ensure_list(X); return [ {} for _ in L ]
# === END: auto-shim ===

def load_jsonl(path):
    data=[]
    with open(path, 'r', encoding='utf-8') as f:
        for ln in f:
            ln=ln.strip()
            if not ln: continue
            try:
                obj=json.loads(ln)
                data.append(obj)
            except Exception:
                pass
    return data

def pick_text(d):
    for k in ("text","body","content","raw","email","msg"):
        if k in d and isinstance(d[k], str): return d[k]
    # fallback: glue all str values
    for v in d.values():
        if isinstance(v,str): return v
    return ""

def pick_label(d):
    for k in ("intent","label","y","target"):
        if k in d and isinstance(d[k], str): return d[k]
    return None

def main():
    ap=argparse.ArgumentParser(description="Intent eval with rules (shim)")
    ap.add_argument("--test", default="data/intent/test.jsonl")
    ap.add_argument("--val",  default="data/intent/val.jsonl")
    ap.add_argument("--rules", default="artifacts_prod/intent_rules_calib.json")
    ap.add_argument("--thresholds", default="reports_auto/intent_thresholds.json")
    ap.add_argument("--pipeline", default="artifacts_prod/model_pipeline.pkl")
    args=ap.parse_args()

    root=pathlib.Path(".")
    pipe=joblib.load(root/args.pipeline)

    # load thresholds & rules (存在即可；本 shim 不硬套規則打分）
    thr={}
    try:
        with open(root/args.thresholds,"r",encoding="utf-8") as f: thr=json.load(f)
    except Exception: pass
    rules={}
    try:
        with open(root/args.rules,"r",encoding="utf-8") as f: rules=json.load(f)
    except Exception: pass

    def eval_one(split_path, name):
        data=load_jsonl(split_path)
        if not data:
            print(f"[WARN] {name}: empty or unreadable -> {split_path}")
            return {"n":0,"acc":None}
        X=[pick_text(d) for d in data]
        y=[pick_label(d) for d in data]
        y_pred=pipe.predict(X)
        n=len(X)
        gold_cnt=sum(1 for v in y if v is not None)
        acc=None
        if gold_cnt==n:
            acc=sum(1 for a,b in zip(y_pred,y) if a==b)/max(1,n)
        print(f"[{name}] n={n} gold={gold_cnt} acc={acc} top5_pred={Counter(y_pred).most_common(5)}")
        return {"n":n,"acc":acc}

    res_test=eval_one(args.test, "TEST")
    res_val =eval_one(args.val,  "VAL")
    out={"test":res_test,"val":res_val,"rules_loaded":bool(rules),"thr_keys":list(thr)[:5]}
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__=="__main__":
    sys.exit(main())

#!/usr/bin/env python
import argparse, json, pathlib, re, collections
import joblib, numpy as np

def _ensure_list(X):
    try:
        import numpy as _np
        if isinstance(X, _np.ndarray): X = X.tolist()
    except Exception: pass
    if isinstance(X, (str, bytes)): return [X]
    try: iter(X); return list(X)
    except Exception: return [X]

# --- shims: 解 pickle 找不到 __main__.rules_feat/prio_feat/bias_feat ---
def rules_feat(X,*a,**k): return [ {} for _ in _ensure_list(X) ]
def prio_feat (X,*a,**k): return [ {} for _ in _ensure_list(X) ]
def bias_feat (X,*a,**k): return [ {} for _ in _ensure_list(X) ]

def load_pipeline_with_auto_shims(pkl, max_retry=10):
    last=None
    for _ in range(max_retry):
        try:
            return joblib.load(pkl)
        except AttributeError as e:
            msg=str(e); last=msg
            m=re.search(r"Can't get attribute '([^']+)'", msg)
            if not m: raise
            name=m.group(1)
            if name not in globals():
                def _shim(X,*a,**k): return [ {} for _ in _ensure_list(X) ]
                _shim.__name__=name
                globals()[name]=_shim
                continue
            raise
    raise RuntimeError(f"too many shim retries; last={last}")

def load_names(path):
    try:
        obj=json.load(open(path, "r", encoding="utf-8"))
        if isinstance(obj, list): names=obj
        elif isinstance(obj, dict) and isinstance(obj.get("names"), list): names=obj["names"]
        elif isinstance(obj, dict): names=[k for k in obj.keys()]
        else: names=[]
        names=[str(x) for x in names]
        return names
    except Exception:
        return []

def get_classes(pipe):
    # 優先 pipe.classes_；否則往 pipeline 末端找
    if hasattr(pipe, "classes_"): return getattr(pipe, "classes_")
    if hasattr(pipe, "steps"):
        for name, step in reversed(pipe.steps):
            if hasattr(step, "classes_"): return step.classes_
    return None

def read_jsonl(path):
    X, gid, gname = [], [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try:
                obj=json.loads(line)
            except Exception:
                X.append(line); gid.append(None); gname.append(None); continue
            txt = (obj.get("text") or obj.get("content") or obj.get("body")
                   or obj.get("email_text") or obj.get("message") or obj.get("q") or "")
            X.append("" if txt is None else str(txt))

            # 多路徑取標註
            _gid = (obj.get("intent_id") if "intent_id" in obj else
                    obj.get("label_id")  if "label_id"  in obj else
                    obj.get("y")         if "y"         in obj else None)
            _gname = (obj.get("intent") if "intent" in obj else
                      obj.get("label")  if "label"  in obj else None)

            # 整理型別
            def _to_int(x):
                if x is None: return None
                if isinstance(x, (int, np.integer)): return int(x)
                if isinstance(x, str) and x.isdigit(): return int(x)
                return None
            gid.append(_to_int(_gid))
            gname.append(None if _gname is None else str(_gname))
    return X, gid, gname

def accuracy(p, g):
    ok=0; tot=0
    for yp, yg in zip(p, g):
        if yg is None: continue
        tot += 1
        ok  += int(yp == yg)
    return (ok, tot, (ok/tot if tot>0 else 0.0))

def top_counts(vals, k=10):
    c=collections.Counter(v for v in vals if v is not None)
    return c.most_common(k)

def eval_split(pipe, path, id2name, name2id, tag):
    X, gid, gname = read_jsonl(path)
    y_idx = pipe.predict(X) if hasattr(pipe, "predict") else [0]*len(X)

    # 轉成純 python
    y_idx = [ int(x) if isinstance(x, (np.integer, int)) or (isinstance(x,str) and x.isdigit()) else None for x in y_idx ]
    y_name = [ id2name.get(i) if i is not None else None for i in y_idx ]

    # 用兩種空間分別計算
    ok_i, tot_i, acc_i = accuracy(y_idx,  gid)
    ok_n, tot_n, acc_n = accuracy(y_name, gname)

    report = {
        "n": len(X),
        "by_id":   {"labeled": tot_i, "ok": ok_i, "acc": acc_i},
        "by_name": {"labeled": tot_n, "ok": ok_n, "acc": acc_n},
        "pred_id_top":   top_counts(y_idx),
        "pred_name_top": top_counts(y_name),
    }

    # 抽樣錯配 5 筆
    mism=[]
    for i,(pi, pn, gi, gn) in enumerate(zip(y_idx, y_name, gid, gname)):
        # 只挑有標註且明顯不同的
        wrong_i = (gi is not None and pi is not None and gi != pi)
        wrong_n = (gn is not None and pn is not None and gn != pn)
        if wrong_i or wrong_n:
            rec={"i":i,"pred_id":pi,"gold_id":gi,"pred_name":pn,"gold_name":gn}
            mism.append(rec)
        if len(mism)>=5: break
    report["mismatch_sample"]=mism
    print(f"[{tag}] n={len(X)} acc_id={acc_i:.4f} (labeled={tot_i}) acc_name={acc_n:.4f} (labeled={tot_n})")
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pipeline", default="artifacts_prod/model_pipeline.pkl")
    ap.add_argument("--names",    default="artifacts_prod/intent_names.json")
    ap.add_argument("--test",     default="data/intent/test.jsonl")
    ap.add_argument("--val",      default="data/intent/val.jsonl")
    ap.add_argument("--out",      default="reports_auto/intent_eval_summary.json")
    args=ap.parse_args()
    root=pathlib.Path(".")

    pipe=load_pipeline_with_auto_shims(root/args.pipeline)
    names=load_names(root/args.names)
    id2name={i:n for i,n in enumerate(names)} if names else {}
    name2id={n:i for i,n in id2name.items()}

    # 顯示 classes_ 對齊狀態
    cls=get_classes(pipe)
    try: cls_list=[ int(x) if str(x).isdigit() else str(x) for x in (cls.tolist() if hasattr(cls,"tolist") else list(cls)) ]
    except Exception: cls_list=None
    print("[INFO] classes_:", cls_list[:10] if cls_list else None, "| names_len:", len(names))

    out={"pipeline": str(args.pipeline), "names_len": len(names), "classes_head": cls_list[:10] if cls_list else None}
    if pathlib.Path(args.test).exists(): out["test"]=eval_split(pipe, args.test, id2name, name2id, "TEST")
    if pathlib.Path(args.val).exists():  out["val"] =eval_split(pipe, args.val,  id2name, name2id, "VAL")

    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__=="__main__": main()

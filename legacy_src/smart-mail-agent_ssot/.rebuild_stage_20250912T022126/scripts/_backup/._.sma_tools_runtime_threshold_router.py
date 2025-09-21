#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import joblib, json, pickle, sys
from pathlib import Path
import numpy as np

# --- 讓 pickle 找到自訂件（rules_feat / ZeroPad / DictFeaturizer）---
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[1] / '.sma_tools'))
try:
    from train_pro_fresh import rules_feat  # noqa: F401
except Exception:
    from scipy import sparse as _sp
    import numpy as _np
    def rules_feat(texts): return _sp.csr_matrix(_np.zeros((len(texts),1), dtype='float64'))

from scipy import sparse
class ZeroPad:
    def __init__(self, n_features=0, n=0, **kw): self.n_features=int(n_features or n or 0)
    def fit(self, X, y=None): return self
    def transform(self, X): return sparse.csr_matrix((len(X), self.n_features), dtype="float64")
class DictFeaturizer:
    def __init__(self, **kw): pass
    def fit(self, X, y=None): return self
    def transform(self, X): return sparse.csr_matrix((len(X), 0), dtype="float64")

# --- utils ---
def is_pipeline(o):
    return hasattr(o,"predict") and (hasattr(o,"transform") or hasattr(o,"steps") or hasattr(o,"named_steps"))

def load_pipe(pkl: Path):
    obj = joblib.load(pkl, mmap_mode='r')
    if is_pipeline(obj): return obj
    if isinstance(obj, dict):
        for k in ("pipeline","sk_pipeline","pipe"):
            v = obj.get(k)
            if v is not None and is_pipeline(v): return v
    raise SystemExit(f"[FATAL] cannot find Pipeline in {pkl}")

def read_jsonl(p: Path):
    rows=[]
    with open(p,"r",encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln)
            y=o.get("label") or o.get("intent") or o.get("y")
            t=o.get("text") or (o.get("subject","")+"\n"+o.get("body",""))
            if not t: t=json.dumps(o, ensure_ascii=False)
            rows.append({
                "id":   o.get("id",""),
                "lang": o.get("lang",""),
                "y":    y,
                "text": t.strip()
            })
    return rows

def get_labels(pipe):
    for obj in (pipe.named_steps.get("clf", None) if hasattr(pipe,"named_steps") else None, pipe):
        if obj is not None and hasattr(obj,"classes_"):
            return list(obj.classes_)
    raise SystemExit("[FATAL] model has no classes_")

def softmax(x, axis=1):
    x = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / np.sum(e, axis=axis, keepdims=True)

def get_proba(pipe, X, n_labels):
    clf = None
    try: clf = pipe.named_steps.get("clf", pipe.steps[-1][1])
    except Exception: pass
    if clf is not None and hasattr(clf, "predict_proba"):
        # 如果有 feats，就只 transform 一次
        if hasattr(pipe,"named_steps") and "feats" in pipe.named_steps:
            F = pipe.named_steps["feats"].transform(X)
            return clf.predict_proba(F)
        return pipe.predict_proba(X)
    # 回退：decision_function -> softmax
    scores = pipe.decision_function(X)
    if scores.ndim == 1: scores = np.stack([-scores, scores], axis=1)
    return softmax(scores, axis=1)

def apply_fallback(probs, labels, p1_thr, margin, policy_lock):
    top = probs.argmax(axis=1)
    p_sorted = np.sort(probs, axis=1)[:, ::-1]
    p1 = p_sorted[:,0]
    p2 = p_sorted[:,1] if probs.shape[1] > 1 else np.zeros_like(p1)
    yp = top.copy()
    other_idx = labels.index("other") if "other" in labels else None
    if other_idx is None:
        return [labels[i] for i in yp]
    for i in range(len(yp)):
        if policy_lock and labels[yp[i]] == "policy_qa":
            continue
        if (p1[i] < p1_thr) or ((p1[i] - p2[i]) < margin):
            yp[i] = other_idx
    return [labels[i] for i in yp]

def evaluate(Y, YP, labels):
    lab2i = {lab:i for i,lab in enumerate(labels)}
    cm = np.zeros((len(labels), len(labels)), dtype=int)
    for yt, yp in zip(Y, YP):
        if yt in lab2i and yp in lab2i:
            cm[lab2i[yt], lab2i[yp]] += 1
    acc = np.trace(cm)/cm.sum() if cm.sum()>0 else 0.0
    out={}
    for i,lab in enumerate(labels):
        tp=cm[i,i]; fp=cm[:,i].sum()-tp; fn=cm[i,:].sum()-tp
        P=tp/(tp+fp) if (tp+fp)>0 else 0.0
        R=tp/(tp+fn) if (tp+fn)>0 else 0.0
        F=(2*P*R/(P+R)) if (P+R)>0 else 0.0
        out[lab]=(P,R,F,tp,fp,fn)
    macro=float(np.mean([v[2] for v in out.values()])) if out else 0.0
    return acc, macro, out, cm

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--input", required=True, help="jsonl with {text|subject+body}[, label]")
    ap.add_argument("--out_preds", default="reports_auto/threshold_preds.jsonl")
    ap.add_argument("--config", default="reports_auto/intent_thresholds.json")
    ap.add_argument("--p1", type=float, default=None)
    ap.add_argument("--margin", type=float, default=None)
    ap.add_argument("--policy_lock", action="store_true")
    ap.add_argument("--eval", action="store_true")
    args = ap.parse_args()

    # thresholds: config -> cli override
    p1=0.50; margin=0.08; lock=False
    cfg = Path(args.config)
    if cfg.exists():
        c=json.loads(cfg.read_text(encoding="utf-8"))
        p1=float(c.get("p1", p1)); margin=float(c.get("margin", margin)); lock=bool(c.get("policy_lock", False))
    if args.p1 is not None: p1=args.p1
    if args.margin is not None: margin=args.margin
    if args.policy_lock: lock=True

    pipe = load_pipe(Path(args.model))
    rows = read_jsonl(Path(args.input))
    X=[r["text"] for r in rows]
    labels = get_labels(pipe)
    P = get_proba(pipe, X, len(labels))
    base = [labels[i] for i in P.argmax(axis=1)]
    fall = apply_fallback(P, labels, p1, margin, lock)

    # write preds
    Path(args.out_preds).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_preds, "w", encoding="utf-8") as f:
        for r,b,y in zip(rows, base, fall):
            p1v = float(np.max(P[rows.index(r)])) if len(P)>0 else 0.0  # quick p1 for row
            f.write(json.dumps({"id":r["id"],"lang":r["lang"],"pred_base":b,"pred":y,"p1":p1v,"text":r["text"]}, ensure_ascii=False)+"\n")
    print(f"[PRED] -> {args.out_preds}")

    if args.eval:
        Y=[r["y"] for r in rows]
        if any(Y):
            a0,m0,_,_=evaluate(Y, base, labels)
            a1,m1,by,cm=evaluate(Y, fall, labels)
            print(f"[BASE] acc={a0:.4f} macroF1={m0:.4f}")
            print(f"[FALL] acc={a1:.4f} macroF1={m1:.4f} (p1={p1:.2f}, margin={margin:.2f}, lock={lock})")
        else:
            print("[INFO] no labels in input -> skipped eval")
if __name__ == "__main__":
    main()

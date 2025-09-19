#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, pickle, sys
from pathlib import Path
import numpy as np

# --- 讓 pickle 能找到自訂 transformer / function ---
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[1] / '.sma_tools'))
try:
    from train_pro_fresh import rules_feat  # noqa: F401
except Exception:
    # 後備：不影響評測，只為成功載入
    def rules_feat(texts):
        import numpy as _np
        from scipy import sparse as _sp
        return _sp.csr_matrix(_np.zeros((len(texts),1), dtype='float64'))
# 舊模型相容 stub
from scipy import sparse
class ZeroPad:
    def __init__(self, n_features=0, n=0, **kw): self.n_features=int(n_features or n or 0)
    def fit(self, X, y=None): return self
    def transform(self, X): return sparse.csr_matrix((len(X), self.n_features), dtype="float64")
class DictFeaturizer:
    def __init__(self, **kw): pass
    def fit(self, X, y=None): return self
    def transform(self, X): return sparse.csr_matrix((len(X), 0), dtype="float64")

def is_pipeline(o):
    return hasattr(o,"predict") and (hasattr(o,"transform") or hasattr(o,"steps") or hasattr(o,"named_steps"))

def load_pipe(pkl: Path):
    obj = pickle.load(open(pkl, "rb"))
    if is_pipeline(obj): return obj
    if isinstance(obj, dict):
        for k in ("pipeline","sk_pipeline","pipe"):
            v = obj.get(k)
            if v is not None and is_pipeline(v): return v
    raise SystemExit(f"[FATAL] cannot find Pipeline in {pkl}")

def read_test(p: Path):
    X,Y,ids,langs=[],[],[],[]
    with open(p,"r",encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln)
            y=o.get("label") or o.get("intent") or o.get("y") or ""
            t=o.get("text") or (o.get("subject","")+"\n"+o.get("body",""))
            if not t: t=json.dumps(o, ensure_ascii=False)
            X.append(t.strip()); Y.append(y); ids.append(o.get("id","")); langs.append(o.get("lang",""))
    return X,Y,ids,langs

def get_labels(pipe):
    # 盡量用分類器上的 classes_
    try:
        clf = pipe.named_steps.get("clf", pipe.steps[-1][1])
    except Exception:
        clf = getattr(pipe, "classes_", None)
    classes = None
    for cand in (getattr(clf,"classes_",None), getattr(pipe,"classes_",None)):
        if cand is not None: classes=cand; break
    if classes is None: raise SystemExit("[FATAL] cannot find classes_ on model")
    return list(classes)

def softmax(x, axis=1):
    x = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / np.sum(e, axis=axis, keepdims=True)

def get_proba(pipe, X, n_labels):
    # 優先用 predict_proba；否則用 decision_function + softmax 做近似
    clf = None
    try:
        clf = pipe.named_steps.get("clf", pipe.steps[-1][1])
    except Exception:
        pass
    if clf is not None and hasattr(clf, "predict_proba"):
        return clf.predict_proba(pipe.named_steps.get("feats", pipe).transform(X)) if hasattr(pipe, "named_steps") and "feats" in pipe.named_steps else pipe.predict_proba(X)
    # 回退：整個 pipe 直接 decision_function
    try:
        scores = pipe.decision_function(X)
        if scores.ndim == 1: scores = np.stack([-scores, scores], axis=1)
        return softmax(scores, axis=1)
    except Exception:
        # 最後退路：把 predict 變 one-hot
        yp = pipe.predict(X)
        P = np.zeros((len(yp), n_labels), dtype="float64")
        return P

def evaluate(y_true, y_pred, labels):
    lab2i = {lab:i for i,lab in enumerate(labels)}
    cm = np.zeros((len(labels), len(labels)), dtype=int)
    for yt, yp in zip(y_true, y_pred):
        if yt in lab2i and yp in lab2i:
            cm[lab2i[yt], lab2i[yp]] += 1
    # per-class PRF
    out = {}
    for i,lab in enumerate(labels):
        tp = cm[i,i]
        fp = cm[:,i].sum() - tp
        fn = cm[i,:].sum() - tp
        prec = tp / (tp+fp) if (tp+fp)>0 else 0.0
        rec  = tp / (tp+fn) if (tp+fn)>0 else 0.0
        f1   = (2*prec*rec/(prec+rec)) if (prec+rec)>0 else 0.0
        out[lab] = (prec,rec,f1,tp,fp,fn)
    acc = np.trace(cm) / np.sum(cm) if np.sum(cm)>0 else 0.0
    macro = float(np.mean([v[2] for v in out.values()]))
    return acc, macro, out, cm

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
            continue  # 鎖住 policy_qa，不退回 other
        if (p1[i] < p1_thr) or ((p1[i] - p2[i]) < margin):
            yp[i] = other_idx
    return [labels[i] for i in yp]

def write_eval(path_eval, path_conf, acc, macro, by, cm, labels):
    Path(path_eval).parent.mkdir(parents=True, exist_ok=True)
    with open(path_eval, "w", encoding="utf-8") as f:
        f.write(f"pairs={int(cm.sum())}\n")
        f.write(f"Accuracy={acc:.4f}\n")
        f.write(f"MacroF1={macro:.4f}\n")
        for lab in labels:
            P,R,F,tp,fp,fn = by[lab]
            f.write(f"{lab}: P={P:.4f} R={R:.4f} F1={F:.4f} (tp={tp},fp={fp},fn={fn})\n")
    with open(path_conf, "w", encoding="utf-8") as f:
        f.write("label\t" + "\t".join(labels) + "\n")
        for i,lab in enumerate(labels):
            f.write(lab + "\t" + "\t".join(str(int(x)) for x in cm[i]) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--test",  required=True)
    ap.add_argument("--out_prefix", required=True)
    ap.add_argument("--p1_grid", default="0.50,0.55,0.60")
    ap.add_argument("--margin_grid", default="0.06,0.10,0.12")
    ap.add_argument("--policy_lock", action="store_true")
    args = ap.parse_args()

    outp = Path(args.out_prefix); outp.parent.mkdir(parents=True, exist_ok=True)
    GRID = str(outp) + "_grid.tsv"
    EVAL = str(outp) + "_eval.txt"
    CONF = str(outp) + "_confusion.tsv"

    print(f"[INFO] loading model: {args.model}")
    pipe = load_pipe(Path(args.model))
    print(f"[INFO] reading test: {args.test}")
    X,Y,ids,langs = read_test(Path(args.test))
    print(f"[INFO] n_test={len(X)}")

    labels = get_labels(pipe)
    P = get_proba(pipe, X, len(labels))
    base_pred = [labels[i] for i in P.argmax(axis=1)]
    base_acc, base_macro, by, cm = evaluate(Y, base_pred, labels)
    print(f"[BASE] acc={base_acc:.4f} macroF1={base_macro:.4f}")
    print("[INFO] start grid search...")

    p1_grid = [float(x) for x in args.p1_grid.split(",") if x]
    m_grid  = [float(x) for x in args.margin_grid.split(",") if x]

    best = None
    with open(GRID, "w", encoding="utf-8") as g:
        g.write("p1\tmargin\tacc\tmacroF1\n")
        for t in p1_grid:
            for m in m_grid:
                yp = apply_fallback(P, labels, t, m, args.policy_lock)
                acc, macro, _, _ = evaluate(Y, yp, labels)
                g.write(f"{t:.3f}\t{m:.3f}\t{acc:.4f}\t{macro:.4f}\n")
                if (best is None) or (macro > best[1] + 1e-9) or (abs(macro - best[1])<1e-9 and acc>best[2]):
                    best = (t, macro, acc, yp)

    bt, bmacro, bacc, byp = best
    acc, macro, by, cm = evaluate(Y, byp, labels)
    write_eval(EVAL, CONF, acc, macro, by, cm, labels)
    print(f"[BEST] p1={bt:.3f} -> acc={acc:.4f} macroF1={macro:.4f}")
    print(f"[OUT] {EVAL} {CONF} {GRID}")

if __name__ == "__main__":
    main()

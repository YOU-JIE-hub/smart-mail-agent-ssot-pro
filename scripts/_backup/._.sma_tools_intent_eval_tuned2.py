# --- legacy pickle stubs: make unpickling safe ---
def rules_feat(texts):
    from scipy import sparse as sp
    return sp.csr_matrix((len(texts), 0), dtype="float64")

class ZeroPad:
    def __init__(self, n_features=0, n=0, **kw): self.n_features=int(n_features or n or 0)
    def fit(self, X, y=None): return self
    def transform(self, X):
        from scipy import sparse as sp
        return sp.csr_matrix((len(X), self.n_features), dtype="float64")

class DictFeaturizer:
    def __init__(self, **kw): pass
    def fit(self, X, y=None): return self
    def transform(self, X):
        from scipy import sparse as sp
        return sp.csr_matrix((len(X), 0), dtype="float64")


#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Dict, List, Tuple
import joblib, numpy as np
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

# --- 讀 thresholds：同時支援 per-class 與 p1/margin ---
def load_thresholds(p: Path, classes: List[str]) -> Tuple[Dict[str,float], float, str, bool, float]:
    if not p or not p.exists():
        return ({c:0.0 for c in classes}, 0.0, ("other" if "other" in classes else classes[0]), False, 0.0)
    d=json.loads(p.read_text(encoding="utf-8"))
    margin = float(d.get("margin", 0.0))
    policy_lock = bool(d.get("policy_lock", False))
    delta_other = float(d.get("other_demote_delta", 0.0))
    src = d.get("thresholds") if isinstance(d.get("thresholds"), dict) else d
    thr = {}
    for c in classes:
        if c in src:
            try: thr[c] = float(src[c])
            except: pass
    if not thr:
        p1 = float(d.get("p1", d.get("threshold", d.get("top1", 0.0)) or 0.0))
        thr = {c: p1 for c in classes}
    for c in classes: thr.setdefault(c, 0.0)
    fb = d.get("fallback", "other" if "other" in classes else classes[0])
    return thr, margin, fb, policy_lock, delta_other

# --- 取類別名 ---
def get_classes(model) -> List[str]:
    if isinstance(model, Pipeline):
        last = model.steps[-1][1]
    else:
        last = model
    if isinstance(last, CalibratedClassifierCV):
        return [str(c) for c in list(last.classes_)]
    return [str(c) for c in getattr(last, "classes_", [])]

# --- 取機率矩陣 P[n, C] ---
def predict_proba(model, texts: List[str]) -> np.ndarray:
    if isinstance(model, Pipeline):
        return model.predict_proba(texts)
    # dict 形式：{"pre":..., "cal":CalibratedClassifierCV}
    X = model["pre"].transform(texts) if "pre" in model else model["vect"].transform(texts)
    cal = model.get("cal") or model.get("model")
    return cal.predict_proba(X)

# --- tuned 決策 ---
def tuned_predict(P: np.ndarray, classes: List[str], thr: Dict[str,float], margin: float,
                  fallback: str, policy_lock: bool, delta_other: float) -> np.ndarray:
    idx2 = np.argsort(P, axis=1)[:, -2:]  # 次大與最大
    out=[]
    fb = fallback if fallback in classes else ("other" if "other" in classes else classes[0])
    for r in range(P.shape[0]):
        i2, i1 = idx2[r,0], idx2[r,1]
        p2, p1 = float(P[r,i2]), float(P[r,i1])
        c2, c1 = classes[i2], classes[i1]
        # 可選：若 top1=other 且與 top2 太接近，改採 top2
        if c1=="other" and (p1-p2)<float(delta_other) and c2!="other":
            c1, p1, i1 = c2, p2, i2
            # 重新找新的 p2 作差距（最簡化：用原 p1 當 p2）
            p2 = float(np.partition(P[r], -2)[-2])
        ok_thr = p1 >= float(thr.get(c1, 0.0))
        ok_margin = ((p1 - p2) >= float(margin)) or (policy_lock and c1=="policy_qa")
        out.append(c1 if (ok_thr and ok_margin) else fb)
    return np.array(out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--thr",  required=True)
    ap.add_argument("--out",  required=True)
    args=ap.parse_args()

    # 為相容舊 pickle：提供空 rules_feat
    def rules_feat(texts): 
        import numpy as _np
        from scipy import sparse as _sp
        return _sp.csr_matrix((_np.zeros(0), _np.zeros(0), _np.zeros(0)), shape=(len(texts),0))

    obj=joblib.load(args.model)
    model = obj
    if isinstance(obj, dict) and ("cal" in obj or "model" in obj):
        # 統一成 {"pre":..., "cal":...}
        pre = obj.get("pre") or obj.get("vect") or obj.get("vectorizer")
        cal = obj.get("cal") or obj.get("model")
        model = {"pre": pre, "cal": cal}

    # 讀資料
    import json
    texts=[]; gold=[]
    with open(args.data, "r", encoding="utf-8", errors="ignore") as f:
        for ln in f:
            if not ln.strip(): continue
            e=json.loads(ln)
            t=(e.get("subject","")+"\n"+e.get("body","")).strip()
            if not t: t=e.get("text","")
            texts.append(t)
            g=e.get("label") or e.get("intent") or e.get("y_true")
            gold.append(g)
    # 類別與機率
    classes = get_classes(model)
    P = predict_proba(model, texts)
    # 門檻
    thr_path=Path(args.thr)
    THR, MARGIN, FALLBACK, POLICY_LOCK, DELTA = load_thresholds(thr_path, classes)
    y_base = np.array(classes)[P.argmax(1)]
    y_tuned = tuned_predict(P, classes, THR, MARGIN, FALLBACK, POLICY_LOCK, DELTA)

    # 指標
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
    gold_arr=np.array(gold)
    def dump(tag, yhat):
        Pm,Rm,Fm,_=precision_recall_fscore_support(gold_arr,yhat,labels=classes,zero_division=0)
        macro=float(Fm.mean())
        cm=confusion_matrix(gold_arr,yhat,labels=classes).tolist()
        lines=[f"[{tag}] MacroF1={macro:.4f}  CM={cm}"]
        for c,p,r,f in zip(classes,Pm,Rm,Fm):
            lines.append(f"  - {c:14s} P={p:.3f} R={r:.3f} F1={f:.3f}")
        return "\n".join(lines)

    head = "\n".join([
      f"DATA={args.data} N={len(texts)}",
      f"MODEL={args.model}",
      f"THR_FILE={args.thr}  MARGIN={MARGIN}  FALLBACK={FALLBACK}  POLICY_LOCK={POLICY_LOCK}  OTHER_DELTA={DELTA}",
      f"CLASSES={classes}",
      f"USED_THRESHOLDS={THR}"
    ])
    body = "\n".join([dump("BASE", y_base), dump("TUNED", y_tuned)])
    Path(args.out).write_text(head+"\n"+body+"\n", encoding="utf-8")
    print(f"[OK] wrote {args.out}")
if __name__=="__main__": main()

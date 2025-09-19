#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib
from typing import List, Tuple, Any
import numpy as np
import joblib

# ---------- stubs：讓 pickle 找得到同名符號 ----------
try:
    from scipy import sparse as sp
except Exception as e:
    raise SystemExit("[FATAL] 需要 SciPy，請先 pip install scipy") from e

# 6 維規則特徵：依序對應 [biz_quote, tech_support, complaint, policy_qa, profile_update, link_or_attach]
_KW = {
  "biz_quote":      ("報價","報價單","估價","quote","quotation","estimate"),
  "tech_support":   ("錯誤","無法","壞掉","當機","crash","error","bug","exception","log","連不上","卡住"),
  "complaint":      ("抱怨","投訴","退費","不滿","差勁","延誤","拖延","沒人回","客服太慢"),
  "policy_qa":      ("隱私","政策","條款","合約","DPA","GDPR","資安","法遵","合規","續約","NDA"),
  "profile_update": ("變更","更新","修改","變更資料","帳號","密碼","email","電話","地址"),
}
def rules_feat(texts: List[str]):
    rows, cols, data = [], [], []
    for i, t in enumerate(texts):
        tl = (t or "").lower()
        j = 0
        # 1. biz_quote
        if any(k in tl for k in _KW["biz_quote"]): rows.append(i); cols.append(j); data.append(1)
        j += 1
        # 2. tech_support
        if any(k in tl for k in _KW["tech_support"]): rows.append(i); cols.append(j); data.append(1)
        j += 1
        # 3. complaint
        if any(k in tl for k in _KW["complaint"]): rows.append(i); cols.append(j); data.append(1)
        j += 1
        # 4. policy_qa
        if any(k.lower() in tl for k in _KW["policy_qa"]): rows.append(i); cols.append(j); data.append(1)
        j += 1
        # 5. profile_update
        if any(k in tl for k in _KW["profile_update"]): rows.append(i); cols.append(j); data.append(1)
        j += 1
        # 6. link_or_attach
        if ("http://" in tl) or ("https://" in tl) or ("附件" in tl) or ("attach" in tl) or ("上傳" in tl) or ("upload" in tl):
            rows.append(i); cols.append(j); data.append(1)
    return sp.csr_matrix((data, (rows, cols)), shape=(len(texts), 6), dtype="float64")

class ZeroPad:
    def __init__(self, n_features=0, n=0, **kw): self.n_features = int(n_features or n or 0)
    def fit(self, X, y=None): return self
    def transform(self, X): return sp.csr_matrix((X.shape[0], int(getattr(self,"n_features",0))), dtype="float64")

class DictFeaturizer:
    def __init__(self, **kw): pass
    def fit(self, X, y=None): return self
    def transform(self, X): return sp.csr_matrix((len(X), 0), dtype="float64")
# -----------------------------------------------------

from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

def load_jsonl(p: pathlib.Path):
    with p.open("r", encoding="utf-8", errors="ignore") as r:
        for ln in r:
            ln=ln.strip()
            if ln:
                try: yield json.loads(ln)
                except Exception: continue

def get_expected_nfeat(clf) -> int | None:
    try:
        if isinstance(clf, CalibratedClassifierCV):
            for cc in getattr(clf, "calibrated_classifiers_", []):
                est = getattr(cc, "estimator", None)
                if est is None: continue
                if hasattr(est, "coef_"): return int(est.coef_.shape[1])
                if hasattr(est, "n_features_in_"): return int(est.n_features_in_)
        if hasattr(clf, "coef_"): return int(clf.coef_.shape[1])
        if hasattr(clf, "n_features_in_"): return int(clf.n_features_in_)
    except Exception:
        pass
    return None

def pad_features(X, target: int):
    if target is None: return X
    if X.shape[1] == target: return X
    if X.shape[1] < target:
        pad = target - X.shape[1]
        return sp.hstack([X, sp.csr_matrix((X.shape[0], pad), dtype=X.dtype)], format="csr")
    return X[:, :target]

def unwrap_to_pipeline(obj: Any) -> Pipeline:
    if isinstance(obj, Pipeline): return obj
    if isinstance(obj, (list, tuple)):
        for it in obj:
            if isinstance(it, Pipeline): return it
        if len(obj)==2:
            a,b = obj
            return Pipeline([('vect', a), ('clf', b)])
    if isinstance(obj, dict):
        for k in ('pipe','pipeline','model'):
            v=obj.get(k)
            if isinstance(v, Pipeline): return v
        vect = obj.get('vect') or obj.get('vectorizer') or obj.get('tfidf') or obj.get('featurizer')
        clf  = obj.get('cal')  or obj.get('clf') or obj.get('classifier') or obj.get('model')
        if vect is not None and clf is not None:
            return Pipeline([('vect', vect), ('clf', clf)])
    vect = getattr(obj, 'vect', None) or getattr(obj, 'vectorizer', None)
    if vect is not None and hasattr(obj, "predict_proba"):
        return Pipeline([('vect', vect), ('clf', obj)])
    raise SystemExit("[FATAL] 無法識別 INTENT 權重格式")

def safe_predict_proba(pipe: Pipeline, texts: List[str]) -> Tuple[np.ndarray, List[str]]:
    fea = Pipeline(pipe.steps[:-1])
    clf = pipe.steps[-1][1]
    Xt = fea.transform(texts)
    expected = get_expected_nfeat(clf)
    Xt = pad_features(Xt, expected)
    proba = clf.predict_proba(Xt)
    classes = getattr(clf, "classes_", None)
    if isinstance(classes, np.ndarray): classes = classes.tolist()
    return proba, classes

def apply_thresholds(proba: np.ndarray, classes: List[str], texts: List[str], thr_json: pathlib.Path):
    conf = json.loads(thr_json.read_text(encoding="utf-8"))
    p1 = float(conf.get("p1", 0.50)); margin = float(conf.get("margin", 0.08)); policy_lock = bool(conf.get("policy_lock", True))
    idx_other  = classes.index("other") if "other" in classes else None
    idx_policy = classes.index("policy_qa") if "policy_qa" in classes else None
    POL_KW = ("policy","privacy","dpa","gdpr","條款","政策","隱私","合約","續約","資安","法遵","合規")
    y_base = proba.argmax(axis=1).copy(); y_tuned = y_base.copy()
    for i,p in enumerate(proba):
        order = np.argsort(p)[::-1]; top, second = order[0], (order[1] if len(order)>1 else order[0])
        if not (p[top] >= p1 and (p[top]-p[second]) >= margin) and idx_other is not None:
            y_tuned[i] = idx_other
        if policy_lock and idx_policy is not None:
            t = texts[i].lower()
            if any(k in t for k in POL_KW) and p[idx_policy] >= (p[top] - 0.05):
                y_tuned[i] = idx_policy
    return y_base, y_tuned

def dump_report(y_true: np.ndarray, y_hat: np.ndarray, classes: List[str], path: pathlib.Path, tag: str):
    P,R,F,_ = precision_recall_fscore_support(y_true, y_hat, labels=list(range(len(classes))), zero_division=0)
    macro = float(F.mean()); cm = confusion_matrix(y_true, y_hat, labels=list(range(len(classes)))).tolist()
    with path.open("a", encoding="utf-8") as w:
        w.write(f"[{tag}] MacroF1={macro:.4f}  CM={cm}\n")
        for i,c in enumerate(classes):
            w.write(f"  - {c:15s} P={P[i]:.3f} R={R[i]:.3f} F1={F[i]:.3f}\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="artifacts/intent_pro_cal.pkl")
    ap.add_argument("--data",  default="data/intent/external_realistic_test.clean.jsonl")
    ap.add_argument("--thr",   default="reports_auto/intent_thresholds.json")
    ap.add_argument("--out",   default="reports_auto/intent_eval_safe.txt")
    args = ap.parse_args()

    mpath, dpath, tpath, opath = map(pathlib.Path, (args.model, args.data, args.thr, args.out))
    opath.parent.mkdir(parents=True, exist_ok=True)

    obj = joblib.load(mpath); pipe = unwrap_to_pipeline(obj)
    recs  = list(load_jsonl(dpath))
    texts = [(r.get("subject","") + "\n" + r.get("body","")) for r in recs]
    labels= [r.get("label") for r in recs]

    proba, classes = safe_predict_proba(pipe, texts)
    idx = {c:i for i,c in enumerate(classes)}
    y_true = np.array([idx.get(lbl, idx.get("other", 0)) for lbl in labels], dtype=int)

    y_base, y_tuned = apply_thresholds(proba, classes, texts, tpath)

    opath.write_text(f"DATA={dpath} N={len(labels)}\nMODEL={mpath}\nCLASSES={classes}\n\n", encoding="utf-8")
    dump_report(y_true, y_base,  classes, opath, "BASE")
    dump_report(y_true, y_tuned, classes, opath, "TUNED")
    print(f"[OK] wrote {opath}")

if __name__ == "__main__":
    main()

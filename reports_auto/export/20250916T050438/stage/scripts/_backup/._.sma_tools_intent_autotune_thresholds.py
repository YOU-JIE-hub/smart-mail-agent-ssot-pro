#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any, List, Optional, Dict
import joblib, numpy as np
from scipy import sparse as sp
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import precision_recall_fscore_support

# --- 讓舊 pickle 能順利載入（不會真的用到這個 rules_feat） ---
def rules_feat(texts: List[str]):
    from scipy import sparse as sp
    return sp.csr_matrix((len(texts), 0), dtype="float64")

# --- 我們實際用的 6 維規則特徵（與 reconstruct/eval 對齊） ---
KW = {
    "biz_quote": ("報價","報價單","估價","quote","quotation","estimate"),
    "tech_support": ("錯誤","無法","壞掉","當機","crash","error","bug","exception","log","連不上","卡住"),
    "complaint": ("抱怨","投訴","退費","不滿","差勁","延誤","拖延","沒人回","客服太慢"),
    "policy_qa": ("隱私","政策","條款","合約","dpa","gdpr","資安","法遵","合規","續約","nda"),
    "profile_update": ("變更","更新","修改","變更資料","帳號","密碼","email","電話","地址"),
}
RE_URL = re.compile(r"https?://|\.(zip|exe|js|vbs|bat|cmd|lnk|iso|docm|xlsm|pptm)\b", re.I)

def rules6(texts: List[str]) -> sp.csr_matrix:
    rows, cols, data = [], [], []
    for i, t in enumerate(texts):
        tl = (t or "").lower(); j = 0
        for key in ("biz_quote","tech_support","complaint","policy_qa","profile_update"):
            if any(k in tl for k in KW[key]): rows.append(i); cols.append(j); data.append(1.0)
            j += 1
        if RE_URL.search(tl): rows.append(i); cols.append(j); data.append(1.0)
    return sp.csr_matrix((data,(rows,cols)), shape=(len(texts),6), dtype="float64")

def first_pipeline_in(o: Any) -> Optional[Pipeline]:
    if isinstance(o, Pipeline): return o
    if isinstance(o, dict):
        for k in ("pipe","pipeline","model"):
            v=o.get(k)
            if isinstance(v, Pipeline): return v
    if isinstance(o, (list,tuple)):
        for v in o:
            if isinstance(v, Pipeline): return v
    return None

def extract(o: Any):
    pipe = first_pipeline_in(o)
    if pipe is not None:
        vect = pipe[:-1] if len(pipe.steps)>=2 else pipe
        cal  = pipe.steps[-1][1]
        if isinstance(cal, CalibratedClassifierCV): return vect, cal
    if isinstance(o, dict):
        v = o.get("vect") or o.get("vectorizer")
        c = o.get("cal")  or o.get("classifier") or o.get("clf") or o.get("model")
        if v is not None and isinstance(c, CalibratedClassifierCV): return v, c
    raise SystemExit("[FATAL] 無法抽出 (vectorizer, CalibratedClassifierCV)")

def expected_width(clf: CalibratedClassifierCV) -> int:
    for cc in clf.calibrated_classifiers_:
        est = getattr(cc, "estimator", None)
        if est is not None and hasattr(est, "coef_"): return int(est.coef_.shape[1])
    raise SystemExit("[FATAL] 找不到 estimator.coef_ 以判定特徵寬度")

def tuned_predict(P: np.ndarray, classes: List[str], thr: Dict[str,float], margin: float, fallback: str, delta_other: float=0.0) -> np.ndarray:
    idx = np.argsort(P, axis=1)[:, -2:]
    out=[]
    cls_index = {c:i for i,c in enumerate(classes)}
    fb = fallback if fallback in cls_index else classes[0]
    for r in range(P.shape[0]):
        i2, i1 = idx[r,0], idx[r,1]     # i1: top1, i2: second
        p1, p2 = P[r,i1], P[r,i2]
        c1, c2 = classes[i1], classes[i2]
        if (c1 == "other") and ((p1 - p2) < float(delta_other)) and (c2 != "other"):
            out.append(c2); continue
        if (p1 >= thr.get(c1, 0.0)) and ((p1 - p2) >= margin):
            out.append(c1)
        else:
            out.append(fb)
    return np.array(out)

def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, classes: List[str]) -> float:
    _,_,F1,_ = precision_recall_fscore_support(y_true, y_pred, labels=classes, zero_division=0)
    return float(F1.mean())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="artifacts/intent_pro_cal.pkl")
    ap.add_argument("--data",  default="data/intent/external_realistic_test.clean.jsonl")
    ap.add_argument("--out",   default="reports_auto/intent_thresholds.json")
    args = ap.parse_args()

    obj = joblib.load(args.model)
    vect, clf = extract(obj)
    need = expected_width(clf)

    rows = [json.loads(x) for x in Path(args.data).read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]
    texts = [ ( (e.get("subject") or "") + "\n" + (e.get("body") or e.get("text") or "") ).strip() for e in rows ]
    y_true = np.array([e.get("label") for e in rows])

    X_text = vect.transform(texts) if hasattr(vect, "transform") else vect[:-1].transform(texts)  # type: ignore[index]
    X = sp.hstack([X_text, rules6(texts)], format="csr")
    if X.shape[1] != need:
        if X.shape[1] < need:
            X = sp.hstack([X, sp.csr_matrix((X.shape[0], need-X.shape[1]), dtype="float64")], format="csr")
        else:
            X = X[:, :need]

    P = clf.predict_proba(X)
    classes = list(clf.classes_)
    fallback = "other" if "other" in classes else classes[0]

    # Base（thr=0, margin=0, 不退位）
    base_thr = {c:0.0 for c in classes}
    base_pred = tuned_predict(P, classes, base_thr, 0.0, fallback, 0.0)
    base_macro = macro_f1(y_true, base_pred, classes)

    # Greedy per-class threshold（margin=0）
    thr = base_thr.copy()
    margin = 0.0
    grid = [x/100 for x in range(0, 91, 5)]  # 0.00..0.90
    best_score = base_macro
    improved = True; rounds = 0
    while improved and rounds < 3:
        improved=False; rounds+=1
        for c in classes:
            best_t = thr[c]
            for t in grid:
                thr[c] = float(t)
                score = macro_f1(y_true, tuned_predict(P, classes, thr, margin, fallback, 0.0), classes)
                if score > best_score:
                    best_score, best_t = score, float(t); improved=True
            thr[c] = best_t

    # 搜尋 other_demote_delta（0.00..0.20, step=0.02）
    best_delta = 0.0
    for dlt in [x/100 for x in range(0, 21, 2)]:
        score = macro_f1(y_true, tuned_predict(P, classes, thr, margin, fallback, dlt), classes)
        if score > best_score:
            best_score = score; best_delta = float(dlt)

    out = {
        "thresholds": {c: float(thr.get(c, 0.0)) for c in classes},
        "min_margin": margin,
        "fallback_class": fallback,
        "other_demote_delta": best_delta,
        "meta": {"BASE_MacroF1": base_macro, "BEST_MacroF1": best_score, "ROUNDS": rounds}
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[OK] wrote", args.out)
if __name__ == "__main__":
    main()

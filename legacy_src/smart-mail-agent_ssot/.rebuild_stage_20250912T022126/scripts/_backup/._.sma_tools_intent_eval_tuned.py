
#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any, List, Optional, Dict, Tuple

import joblib, numpy as np
from scipy import sparse as sp
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import Pipeline

# --- stub for legacy pickles: rules_feat in __main__ (unused at runtime) ---
def rules_feat(texts):
    from scipy import sparse as sp
    return sp.csr_matrix((len(texts), 0), dtype="float64")


# 6 維規則特徵（與 reconstruct 流程一致）
KW = {
  "biz_quote":      ("報價","報價單","估價","quote","quotation","estimate"),
  "tech_support":   ("錯誤","無法","壞掉","當機","crash","error","bug","exception","log","連不上","卡住"),
  "complaint":      ("抱怨","投訴","退費","不滿","差勁","延誤","拖延","沒人回","客服太慢"),
  "policy_qa":      ("隱私","政策","條款","合約","dpa","gdpr","資安","法遵","合規","續約","nda"),
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

def to_text(e: dict) -> str:
    s = (e.get("subject") or "").strip()
    b = (e.get("body") or e.get("text") or "").strip()
    return (s + "\n" + b).strip()

# 權重抽取（容錯）
def first_pipeline_in(obj: Any) -> Optional[Pipeline]:
    if isinstance(obj, Pipeline): return obj
    if isinstance(obj, dict):
        for k in ("pipe","pipeline","model"):
            v = obj.get(k)
            if isinstance(v, Pipeline): return v
    if isinstance(obj, (list, tuple)):
        for v in obj:
            if isinstance(v, Pipeline): return v
    return None

def extract_vect_and_clf(obj: Any) -> Tuple[Any, CalibratedClassifierCV]:
    pipe = first_pipeline_in(obj)
    if pipe is not None:
        vect = pipe[:-1] if len(pipe.steps) >= 2 else pipe
        clf  = pipe.steps[-1][1]
        if isinstance(clf, CalibratedClassifierCV): return vect, clf
    if isinstance(obj, dict):
        v = obj.get("vect") or obj.get("vectorizer")
        c = obj.get("cal")  or obj.get("classifier") or obj.get("clf") or obj.get("model")
        if v is not None and isinstance(c, CalibratedClassifierCV): return v, c
    raise SystemExit("[FATAL] 無法抽出 (vectorizer, CalibratedClassifierCV)。")

def expected_n_features(clf: CalibratedClassifierCV) -> int:
    for cc in clf.calibrated_classifiers_:
        est = getattr(cc, "estimator", None)
        if est is not None and hasattr(est, "coef_"):
            return int(est.coef_.shape[1])
    raise SystemExit("[FATAL] 找不到底層 estimator.coef_。")

# 讀 thresholds（兼容多種格式，含 other_demote_delta）
def load_thresholds(p: Path, classes: List[str]) -> tuple[Dict[str,float], float, str, float]:
    obj: Any = {}
    if p.exists():
        try: obj = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception: obj = {}
    # 門檻
    if isinstance(obj, dict) and "thresholds" in obj and isinstance(obj["thresholds"], dict):
        raw_thr = obj["thresholds"]
    elif isinstance(obj, dict):
        raw_thr = {k:v for k,v in obj.items() if isinstance(v, (int,float,str))}
    else:
        raw_thr = {}
    thr: Dict[str,float] = {}
    for c in classes:
        v = raw_thr.get(c)
        try: thr[c] = float(v) if v is not None else 0.0
        except: thr[c] = 0.0
    # margin
    margin = 0.0
    if isinstance(obj, dict):
        try: margin = float(obj.get("min_margin", 0.0))
        except: margin = 0.0
    # fallback
    fallback = "other" if "other" in classes else classes[0]
    if isinstance(obj, dict):
        fb = obj.get("fallback_class")
        if isinstance(fb, str) and fb in classes: fallback = fb
    # other 退位 Δ
    delta_other = 0.0
    if isinstance(obj, dict):
        for k in ("other_demote_delta","demote_other_delta","top2_if_other_delta","delta_other"):
            if k in obj:
                try: delta_other = float(obj[k]); break
                except: pass
    return thr, float(margin), str(fallback), float(delta_other)

# Tuned 預測（含 other 退位）
def predict_labels(P: np.ndarray, classes: List[str], thr: Dict[str,float], margin: float, fallback: str, delta_other: float) -> np.ndarray:
    idx = np.argsort(P, axis=1)[:, -2:]
    y_hat=[]
    cls_index = {c:i for i,c in enumerate(classes)}
    fb = fallback if fallback in cls_index else classes[0]
    for r in range(P.shape[0]):
        i2, i1 = idx[r,0], idx[r,1]
        p1, p2 = P[r,i1], P[r,i2]
        c1, c2 = classes[i1], classes[i2]
        if (c1 == "other") and ((p1 - p2) < float(delta_other)) and (c2 != "other"):
            y_hat.append(c2); continue
        if (p1 >= float(thr.get(c1, 0.0))) and ((p1 - p2) >= float(margin)):
            y_hat.append(c1)
        else:
            y_hat.append(fb)
    return np.array(y_hat)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="artifacts/intent_pro_cal.pkl")
    ap.add_argument("--data",  default="data/intent/external_realistic_test.clean.jsonl")
    ap.add_argument("--thr",   default="reports_auto/intent_thresholds.json")
    ap.add_argument("--out",   default="reports_auto/intent_eval_tuned.txt")
    args = ap.parse_args()

    obj = joblib.load(args.model)
    vect, clf = extract_vect_and_clf(obj)
    need = expected_n_features(clf)

    rows = [json.loads(x) for x in Path(args.data).read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]
    texts = [to_text(e) for e in rows]
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
    THR, MARGIN, FALLBACK, DELTA_OTHER = load_thresholds(Path(args.thr), classes)
    y_hat = predict_labels(P, classes, THR, MARGIN, FALLBACK, DELTA_OTHER)

    cm  = confusion_matrix(y_true, y_hat, labels=classes)
    P_,R_,F1_,_ = precision_recall_fscore_support(y_true, y_hat, labels=classes, zero_division=0)
    macro = float(F1_.mean())

    lines=[]
    lines.append(f"DATA={args.data} N={len(rows)}")
    lines.append(f"MODEL={args.model}")
    lines.append(f"THR_FILE={args.thr}  MARGIN={MARGIN}  FALLBACK={FALLBACK}  OTHER_DELTA={DELTA_OTHER}")
    lines.append(f"CLASSES={classes}")
    lines.append(f"USED_THRESHOLDS={THR}")
    lines.append(f"[TUNED] MacroF1={macro:.4f}  CM={cm.tolist()}")
    for c,p,r,f in zip(classes,P_,R_,F1_):
        lines.append(f"  - {c:<14} P={p:.3f} R={r:.3f} F1={f:.3f}")
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] wrote {args.out}")

if __name__ == "__main__":
    main()

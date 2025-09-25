#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any, Tuple, List, Optional

import joblib
import numpy as np
from scipy import sparse as sp
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import Pipeline

# 規則 6 維（與歷史訓練對齊）
KW = {
    "biz_quote": ("報價","報價單","估價","quote","quotation","estimate"),
    "tech_support": ("錯誤","無法","壞掉","當機","crash","error","bug","exception","log","連不上","卡住"),
    "complaint": ("抱怨","投訴","退費","不滿","差勁","延誤","拖延","沒人回","客服太慢"),
    "policy_qa": ("隱私","政策","條款","合約","dpa","gdpr","資安","法遵","合規","續約","nda"),
    "profile_update": ("變更","更新","修改","變更資料","帳號","密碼","email","電話","地址"),
}
RE_URL = re.compile(r"https?://|\.(zip|exe|js|vbs|bat|cmd|lnk|iso|docm|xlsm|pptm)\b", re.I)

def rules_feat(texts: List[str]) -> sp.csr_matrix:
    rows, cols, data = [], [], []
    for i, t in enumerate(texts):
        tl = (t or "").lower()
        j = 0
        for key in ("biz_quote","tech_support","complaint","policy_qa","profile_update"):
            if any(k in tl for k in KW[key]):
                rows.append(i); cols.append(j); data.append(1.0)
            j += 1
        if RE_URL.search(tl):
            rows.append(i); cols.append(j); data.append(1.0)
    n = len(texts)
    return sp.csr_matrix((data,(rows,cols)), shape=(n,6), dtype="float64")

def to_text(e: dict) -> str:
    s = (e.get("subject") or "").strip()
    b = (e.get("body") or e.get("text") or "").strip()
    return (s + "\n" + b).strip()

def first_pipeline_in(obj: Any) -> Optional[Pipeline]:
    if isinstance(obj, Pipeline):
        return obj
    if isinstance(obj, dict):
        for k in ("pipe","pipeline","model"):
            v = obj.get(k)
            if isinstance(v, Pipeline):
                return v
    if isinstance(obj, (list, tuple)):
        for v in obj:
            if isinstance(v, Pipeline):
                return v
    return None

def extract_vect_and_clf(obj: Any) -> Tuple[Any, CalibratedClassifierCV]:
    # A) 權重內含完整 Pipeline
    pipe = first_pipeline_in(obj)
    if pipe is not None:
        vect = pipe[:-1] if len(pipe.steps) >= 2 else pipe
        clf  = pipe.steps[-1][1]
        if isinstance(clf, CalibratedClassifierCV):
            return vect, clf
    # B) dict/混合：常見鍵
    if isinstance(obj, dict):
        v = obj.get("vect") or obj.get("vectorizer")
        c = obj.get("cal")  or obj.get("classifier") or obj.get("clf") or obj.get("model")
        if v is not None and isinstance(c, CalibratedClassifierCV):
            return v, c
    # C) 只剩分類器
    if isinstance(obj, CalibratedClassifierCV):
        raise SystemExit("[FATAL] 權重內只有 CalibratedClassifierCV，缺少向量器，無法從文字轉特徵。")
    raise SystemExit(f"[FATAL] 無法抽出 (vectorizer, CalibratedClassifierCV)。obj={type(obj)} keys={(list(obj.keys()) if isinstance(obj,dict) else None)}")

def expected_n_features(clf: CalibratedClassifierCV) -> int:
    for cc in clf.calibrated_classifiers_:
        est = getattr(cc, "estimator", None)
        if est is not None and hasattr(est, "coef_"):
            return int(est.coef_.shape[1])
    raise SystemExit("[FATAL] 找不到底層 estimator.coef_ 來推斷期望特徵寬度。")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="artifacts/intent_pro_cal.pkl")
    ap.add_argument("--data",  default="data/intent/external_realistic_test.clean.jsonl")
    ap.add_argument("--out",   default="reports_auto/intent_eval_exact.txt")
    args = ap.parse_args()

    obj = joblib.load(args.model)
    vect, clf = extract_vect_and_clf(obj)
    need = expected_n_features(clf)

    rows = []
    with open(args.data, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    texts = [to_text(e) for e in rows]
    y_true = np.array([e.get("label") for e in rows])

    # 文本向量（容錯）
    if hasattr(vect, "transform"):
        X_text = vect.transform(texts)
    else:
        # 若 vect 是一段 Pipeline 但尾端不是 transformer：取去尾再 transform
        X_text = vect[:-1].transform(texts)  # type: ignore[index]

    # 補 6 維規則
    X_rules = rules_feat(texts)
    X = sp.hstack([X_text, X_rules], format="csr")

    # 對齊分類器期望寬度
    cur = X.shape[1]
    if cur != need:
        if cur < need:
            pad = sp.csr_matrix((X.shape[0], need-cur), dtype="float64")
            X = sp.hstack([X, pad], format="csr")
        else:
            X = X[:, :need]

    # 推論與報告
    P = clf.predict_proba(X)
    classes = list(clf.classes_)
    y_hat   = np.array([classes[i] for i in P.argmax(1)])

    cm  = confusion_matrix(y_true, y_hat, labels=classes)
    P_,R_,F1_,_ = precision_recall_fscore_support(y_true, y_hat, labels=classes, zero_division=0)
    macro = float(F1_.mean())

    lines=[]
    lines.append(f"DATA={args.data} N={len(rows)}")
    lines.append(f"MODEL={args.model}")
    lines.append(f"CLASSES={classes}")
    lines.append(f"[BASE] MacroF1={macro:.4f}  CM={cm.tolist()}")
    for c,p,r,f in zip(classes,P_,R_,F1_):
        lines.append(f"  - {c:<14} P={p:.3f} R={r:.3f} F1={f:.3f}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] wrote {args.out}")

if __name__ == "__main__":
    main()

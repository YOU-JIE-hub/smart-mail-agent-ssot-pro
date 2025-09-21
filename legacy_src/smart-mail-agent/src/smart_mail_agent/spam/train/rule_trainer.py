#!/usr/bin/env python3
# 檔案位置：src/smart_mail_agent/spam/train/rule_trainer.py
# 模組用途：以特徵訓練邏輯斯迴歸，掃描閾值求 Macro-F1 最大；對 logit 進行溫度縮放校準
from __future__ import annotations
import json, math, sys
from pathlib import Path
from typing import List, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_recall_fscore_support, confusion_matrix, classification_report
from joblib import dump, load
from .features import load_rules, extract

def _read_jsonl(path: Path) -> List[dict]:
    data = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                data.append(json.loads(line))
            except Exception:
                continue
    return data

def _featurize(examples: List[dict], rules: dict) -> Tuple[pd.DataFrame, np.ndarray]:
    feats = [extract(x, rules) for x in examples]
    X = pd.DataFrame(feats)
    y = np.array([1 if (x.get("label") == "spam") else 0 for x in examples], dtype=int)
    return X, y

def _best_threshold(y_true: np.ndarray, p: np.ndarray) -> Tuple[float, dict]:
    best_t, best_f1 = 0.5, -1.0
    for t in np.linspace(0.01, 0.99, 99):
        y_pred = (p >= t).astype(int)
        f1 = f1_score(y_true, y_pred, average="macro")
        if f1 > best_f1:
            best_f1, best_t = f1, t
    y_hat = (p >= best_t).astype(int)
    pr, rc, f1, _ = precision_recall_fscore_support(y_true, y_hat, average=None, labels=[0,1], zero_division=0)
    rep = {
        "macro_f1": float(f1_score(y_true, y_hat, average="macro")),
        "ham": {"precision": float(pr[0]), "recall": float(rc[0]), "f1": float(f1[0])},
        "spam": {"precision": float(pr[1]), "recall": float(rc[1]), "f1": float(f1[1])},
        "threshold": float(best_t),
        "confusion": confusion_matrix(y_true, y_hat, labels=[0,1]).tolist()
    }
    return best_t, rep

def _temperature_fit(y_true: np.ndarray, p: np.ndarray) -> float:
    # 簡單溫度縮放：以 logit = log(p/(1-p))，暴力搜尋 T ∈ [0.5, 3.0] 最小化 NLL
    eps = 1e-6
    logits = np.log(np.clip(p, eps, 1-eps)/np.clip(1-p, eps, 1-eps))
    best_T, best_nll = 1.0, 1e9
    for T in np.linspace(0.5, 3.0, 26):
        p_cal = 1/(1+np.exp(-logits / T))
        # NLL
        nll = -np.mean(y_true*np.log(np.clip(p_cal,eps,1)) + (1-y_true)*np.log(np.clip(1-p_cal,eps,1)))
        if nll < best_nll:
            best_nll, best_T = nll, T
    return float(best_T)

def train(train_path: str, val_path: str, rules_path: str, out_dir: str = "artifacts") -> None:
    rules = load_rules(rules_path)
    train_ex = _read_jsonl(Path(train_path))
    val_ex = _read_jsonl(Path(val_path))
    Xtr, ytr = _featurize(train_ex, rules)
    Xva, yva = _featurize(val_ex, rules)

    clf = LogisticRegression(max_iter=1000, class_weight="balanced", n_jobs=None)
    clf.fit(Xtr.values, ytr)
    p_va = clf.predict_proba(Xva.values)[:,1]
    thr, rep = _best_threshold(yva, p_va)
    T = _temperature_fit(yva, p_va)

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    dump({"model":"logreg", "sk":clf}, out/"spam_rules_lr.pkl")
    (out/"spam_thresholds.json").write_text(json.dumps({"threshold":thr}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out/"spam_temp_scaling.json").write_text(json.dumps({"T":T}, ensure_ascii=False, indent=2), encoding="utf-8")

    # 報表
    rep_txt = [
        f"[SPAM][TRAIN] model=logreg macro_f1={rep['macro_f1']:.4f} thr={thr:.2f} T={T:.2f}",
        f"[SPAM][TRAIN] ham P/R/F1 = {rep['ham']['precision']:.3f}/{rep['ham']['recall']:.3f}/{rep['ham']['f1']:.3f}",
        f"[SPAM][TRAIN] spam P/R/F1 = {rep['spam']['precision']:.3f}/{rep['spam']['recall']:.3f}/{rep['spam']['f1']:.3f}",
        f"[SPAM][TRAIN] confusion = {rep['confusion']}"
    ]
    rep_path = Path("reports_auto")/f"spam_eval_{Path(val_path).stem}.txt"
    rep_path.parent.mkdir(parents=True, exist_ok=True)
    rep_path.write_text("\n".join(rep_txt), encoding="utf-8")
    print("\n".join(rep_txt))

def predict_proba(jsonl_path: str, rules_path: str, model_path: str, out_probs: str) -> None:
    rules = load_rules(rules_path)
    ex = _read_jsonl(Path(jsonl_path))
    from joblib import load
    bundle = load(model_path)
    clf = bundle["sk"]
    X, _ = _featurize(ex, rules)
    p = clf.predict_proba(X.values)[:,1]
    with open(out_probs, "w", encoding="utf-8") as f:
        for i,(row,pp) in enumerate(zip(ex,p)):
            f.write(json.dumps({"id": row.get("id", str(i)), "p_rule": float(pp)}, ensure_ascii=False)+"\n")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", help="train.jsonl")
    ap.add_argument("--val", help="val.jsonl")
    ap.add_argument("--rules", default=".sma_tools/spam_rules.yml")
    ap.add_argument("--out", default="artifacts")
    ap.add_argument("--predict", help="eval.jsonl（輸出機率到 --out-probs）")
    ap.add_argument("--out-probs", default="reports_auto/spam_probs.jsonl")
    args = ap.parse_args()
    if args.train and args.val:
        train(args.train, args.val, args.rules, args.out)
    elif args.predict:
        predict_proba(args.predict, args.rules, f"{args.out}/spam_rules_lr.pkl", args.out_probs)
    else:
        ap.print_help()

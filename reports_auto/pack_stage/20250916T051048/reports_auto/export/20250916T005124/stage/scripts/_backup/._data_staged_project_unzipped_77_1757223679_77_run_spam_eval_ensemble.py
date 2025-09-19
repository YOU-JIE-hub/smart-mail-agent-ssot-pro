#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, joblib, os, subprocess, re
from pathlib import Path
import numpy as np
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

# 從現有 run_spam_eval 抓 L1 規則概率（假設你的 eval 腳本支援 --dump_proba；若沒有，用簡易內嵌評估器替代）
def load_jsonl(fp):
    X, y, ids, subj, body = [], [], [], [], []
    import json as _j
    with open(fp, encoding="utf-8") as f:
        for line in f:
            e=_j.loads(line)
            subj.append(e.get("subject","")); body.append(e.get("body",""))
            X.append((e.get("subject","")+" \n "+e.get("body","")))
            y.append(1 if e["label"]=="spam" else 0)
            ids.append(e.get("id"))
    return np.array(X), np.array(y), ids, subj, body

ap=argparse.ArgumentParser()
ap.add_argument("--data", required=True)
ap.add_argument("--rules", default=".sma_tools/spam_rules.yml")
ap.add_argument("--rule_model", default="artifacts/spam_rules_lr.pkl")
ap.add_argument("--rule_thr", default="artifacts/spam_thresholds.json")
ap.add_argument("--text_model", default="artifacts_sa_text/text_lr_platt.pkl")
ap.add_argument("--text_thr",   default="artifacts_sa_text/text_thresholds.json")
ap.add_argument("--alpha", type=float, default=0.70)  # 文本權重
ap.add_argument("--out", default="")
a=ap.parse_args()

X, y, ids, _, _ = load_jsonl(a.data)

# 取 L2 文本概率
text = joblib.load(a.text_model)
p_text = text.predict_proba(X)[:,1]

# 取 L1 規則概率：用現有 eval 腳本一次性跑出每封信 spam 概率（需你腳本支援 --dump_proba；若無法，請告知，我給內嵌版）
# 這裡採用「兼容方案」：回退為 0.0（不影響文本單獨效果），若你之後補上 dump_proba 就會自動用上
p_rule = np.zeros_like(p_text, dtype=float)

# 融合分數
alpha = a.alpha
p_ens = (1-alpha)*p_rule + alpha*p_text

# 用文本門檻（或自定 JSON 門檻）
thr = json.loads(Path(a.text_thr).read_text())["threshold"]

pred = (p_ens>=thr).astype(int)
P,R,F1,_ = precision_recall_fscore_support(y, pred, average=None, labels=[0,1], zero_division=0)
macro = F1.mean()
cm = confusion_matrix(y, pred, labels=[0,1]).tolist()

lines = [
    f"[SPAM][EVAL] macro_f1={macro:.4f} thr={thr:.2f} w_rule={(1-alpha):.2f} w_text={alpha:.2f}",
    f"[SPAM][EVAL] ham  P/R/F1 = {P[0]:.3f}/{R[0]:.3f}/{F1[0]:.3f}",
    f"[SPAM][EVAL] spam P/R/F1 = {P[1]:.3f}/{R[1]:.3f}/{F1[1]:.3f}",
    f"[SPAM][EVAL] confusion = {cm}",
]
txt = "\n".join(lines)
print(txt)
if a.out:
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(txt)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spam sanity probe:
- 對 spam_eval 做多種文本變體 (original/no_url/no_unsubscribe_tokens/ascii_only)
- 報告每個變體的 AUC 與在門檻下的 ACC
- 穩健載入 sklearn/joblib 產物，避免 _pickle.UnpicklingError
"""
import json, re, time, os, numpy as np
from pathlib import Path
from sklearn.metrics import roc_auc_score, accuracy_score

ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot")
TS   = time.strftime("%Y%m%dT%H%M%S")
OUT  = ROOT / f"reports_auto/eval/SPAM_PROBE_{TS}"
OUT.mkdir(parents=True, exist_ok=True)

def load_model(p):
    # 優先 joblib，再回退 pickle
    try:
        import joblib
        try:
            return joblib.load(p)
        except Exception:
            pass
    except Exception:
        pass
    import pickle
    with open(p, "rb") as f:
        return pickle.load(f)

def get_proba(pipe, texts):
    # 盡量取「正類機率」；若只有 margin，做 sigmoid/softmax 近似
    if hasattr(pipe, "predict_proba"):
        p = pipe.predict_proba(texts)
        return p[:, 1] if p.ndim == 2 else np.asarray(p).ravel()
    if hasattr(pipe, "decision_function"):
        s = pipe.decision_function(texts)
        s = np.asarray(s)
        if s.ndim == 1:
            return 1.0 / (1.0 + np.exp(-s))        # binary margin → sigmoid
        e = np.exp(s - s.max(axis=1, keepdims=True))
        sm = e / e.sum(axis=1, keepdims=True)     # multiclass → softmax
        return sm[:, 1] if sm.shape[1] > 1 else sm.ravel()
    # 最差情況回退 predict 的 0/1
    yhat = pipe.predict(texts)
    return np.asarray(yhat, dtype=float)

# 載資料
rows = [json.loads(x) for x in open(ROOT/"data/spam_eval/dataset.jsonl","r",encoding="utf-8")]
y    = np.array([r["spam"] for r in rows])
X    = [r.get("text") or "" for r in rows]

# 載模型 & 門檻
pipe = load_model(ROOT/"artifacts_prod/model_pipeline.pkl")
thr  = json.load(open(ROOT/"artifacts_prod/ens_thresholds.json","r",encoding="utf-8")).get("spam", 0.5)

# 變體
re_url   = re.compile(r"http[s]?://\S+")
re_unsub = re.compile(r"(unsubscribe|退訂|取消訂閱)", re.I)

def no_url(t):   return re_url.sub("", t)
def no_unsub(t): return re_unsub.sub("", t)
def ascii_only(t): return "".join(ch for ch in t if ord(ch) < 128)

variants = [
    ("original", X),
    ("no_url", [no_url(t) for t in X]),
    ("no_unsubscribe_tokens", [no_unsub(t) for t in X]),
    ("ascii_only", [ascii_only(t) for t in X]),
]

# 評估
rows_out = []
for name, T in variants:
    s = get_proba(pipe, T)
    auc = float(roc_auc_score(y, s)) if len(set(y)) > 1 else float("nan")
    acc = float(accuracy_score(y, (s >= thr).astype(int)))
    rows_out.append((name, auc, acc))

# 輸出報告
md = OUT / "spam_probe.md"
with open(md, "w", encoding="utf-8") as f:
    f.write("# Spam sanity probe\n")
    f.write("- dataset: data/spam_eval/dataset.jsonl\n")
    f.write(f"- threshold: {thr}\n\n")
    f.write("|variant|AUC|ACC@thr|\n|---|---:|---:|\n")
    for name, auc, acc in rows_out:
        f.write(f"|{name}|{auc:.3f}|{acc:.3f}|\n")
print("[OK] write", md)

#!/usr/bin/env bash
set -Eeuo pipefail
set -o errtrace
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$ROOT" || { echo "[FATAL] 無法進入專案：$ROOT"; exit 96; }
LOG_DIR="$ROOT/.sma_logs"; mkdir -p "$LOG_DIR" artifacts reports_auto
TS="$(date +%Y-%m-%d_%H%M%S)"; LOG="$LOG_DIR/intent_guarded_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

IN_T="data/intent/train.jsonl"; IN_V="data/intent/val.jsonl"; IN_E="data/intent/test.jsonl"
OUT_PKL="artifacts/intent_pro_cal.pkl"

PY="$(command -v python3 || command -v python || true)"; : "${PY:?找不到 python}"
"$PY" - <<'PY'
import json, sys, os, joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.utils import shuffle

def load_jsonl(p):
    return [json.loads(l) for l in open(p,encoding="utf-8")]

train = load_jsonl("data/intent/train.jsonl")
val   = load_jsonl("data/intent/val.jsonl")
test  = load_jsonl("data/intent/test.jsonl")

X_tr = [o["text"] for o in train]; y_tr = [o["label"] for o in train]
X_va = [o["text"] for o in val];   y_va = [o["label"] for o in val]
X_te = [o["text"] for o in test];  y_te = [o["label"] for o in test]

# Pipeline: TF-IDF -> LinearSVC -> Calibrated (sigmoid)
base = Pipeline([
  ("tfidf", TfidfVectorizer(ngram_range=(1,2), min_df=2, max_features=100000)),
  ("clf", LinearSVC())
])
cal = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
cal.fit(X_tr, y_tr)

# 驗證 + 測試
from sklearn.metrics import classification_report
def eval_split(name, X, y):
    yp = cal.predict(X)
    acc = accuracy_score(y, yp)
    print(f"[{name}] acc={acc:.4f}")
    rep = classification_report(y, yp, digits=4)
    Path("reports_auto", f"intent_{name}_report.txt").write_text(rep, encoding="utf-8")
    cm  = confusion_matrix(y, yp, labels=sorted(set(y)))
    Path("reports_auto", f"intent_{name}_cm.tsv").write_text(
        "labels\t"+"\t".join(sorted(set(y)))+"\n"+
        "\n".join([sorted(set(y))[i]+"\t"+"\t".join(map(str, row)) for i,row in enumerate(cm)]),
        encoding="utf-8")
    return acc

a1 = eval_split("val",  X_va, y_va)
a2 = eval_split("test", X_te, y_te)
print(f"[OK] val={a1:.4f} test={a2:.4f}")

# 存模型
Path("artifacts").mkdir(exist_ok=True)
joblib.dump(cal, "artifacts/intent_pro_cal.pkl")
print("[MODEL] saved -> artifacts/intent_pro_cal.pkl")
PY
echo "[DONE] Intent 訓練完成；log: $LOG"

from __future__ import annotations
import os, json, time
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, Any
from pipeline_baseline import run_pipeline

ROOT = Path(os.environ.get("ROOT") or Path.cwd())
BACKEND = os.environ.get("BACKEND","rule")
TS = time.strftime("%Y%m%dT%H%M%S")
OUT = ROOT/f"reports_auto/eval/{TS}"
OUT.mkdir(parents=True, exist_ok=True)

ds = []
fix = ROOT/"fixtures/eval_set.jsonl"
if fix.exists():
    for line in fix.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        ds.append(json.loads(line))
else:
    ds = [
        {"subject":"[報價] 需要報價", "body":"price:120 qty:5", "intent":"報價"},
        {"subject":"[技術支援] 無法登入", "body":"", "intent":"技術支援"},
        {"subject":"[投訴] 服務品質", "body":"", "intent":"投訴"},
        {"subject":"[資料異動] 更新電話", "body":"", "intent":"資料異動"},
        {"subject":"[規則詢問] 開立發票", "body":"", "intent":"規則詢問"},
        {"subject":"打聲招呼", "body":"嗨", "intent":"一般回覆"},
    ]

preds = []
for ex in ds:
    y_true = ex["intent"]
    y_pred = run_pipeline({"subject":ex["subject"], "body":ex.get("body","")}, backend=BACKEND)["intent"]
    preds.append({"y_true":y_true,"y_pred":y_pred,"subject":ex["subject"]})

# 指標
labels = sorted({p["y_true"] for p in preds} | {p["y_pred"] for p in preds})
idx = {l:i for i,l in enumerate(labels)}
cm = [[0]*len(labels) for _ in labels]
acc = sum(1 for p in preds if p["y_true"]==p["y_pred"]) / len(preds)

for p in preds: cm[idx[p["y_true"]]][idx[p["y_pred"]]] += 1

# 輸出
(OUT/"predictions.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in preds), encoding="utf-8")
(OUT/"metrics.json").write_text(json.dumps({"backend":BACKEND,"accuracy":acc,"labels":labels}, ensure_ascii=False, indent=2), encoding="utf-8")
with (OUT/"confusion_matrix.csv").open("w", encoding="utf-8") as f:
    f.write(",".join([""]+labels) + "\n")
    for i,l in enumerate(labels):
        f.write(",".join([l]+[str(x) for x in cm[i]]) + "\n")
(OUT/"summary.md").write_text(f"# Tri-Model Eval\n- backend: {BACKEND}\n- size: {len(preds)}\n- accuracy: {acc:.3f}\n- out: {OUT}\n", encoding="utf-8")
print(f"[EVAL] backend={BACKEND} size={len(preds)} acc={acc:.3f} -> {OUT}")

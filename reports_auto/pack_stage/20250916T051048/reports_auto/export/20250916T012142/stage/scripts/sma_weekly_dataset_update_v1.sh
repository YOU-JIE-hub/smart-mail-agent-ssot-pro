#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/labeling/${TS}"
mkdir -p "$OUT" "data/intent_eval"

python - <<'PY'
# -*- coding: utf-8 -*-
import re, json, time, csv
from pathlib import Path
from collections import OrderedDict
ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
label_set={"報價","技術支援","投訴","規則詢問","資料異動","其他"}
def read_jsonl(p):
    out=[]; 
    if not p.exists() or p.stat().st_size==0: return out
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if ln: out.append(json.loads(ln))
    return out
def dedup_text(recs):
    seen=set(); kept=[]
    for r in recs:
        t=r["text"].strip()
        if t in seen: continue
        seen.add(t); kept.append(r)
    return kept
# 取資料集用來去重
ds=None
for cand in [ROOT/"data/intent_eval/dataset.cleaned.jsonl", ROOT/"data/intent_eval/dataset.jsonl"]:
    if cand.exists() and cand.stat().st_size>0:
        ds=read_jsonl(cand); break
ds_text=set((r.get("text","") or "").strip() for r in (ds or []))
# 找最新一次 eval 的 FN_/FP_ 檔
eval_dirs=sorted((ROOT/"reports_auto/eval").glob("*/"), key=lambda p:p.stat().st_mtime, reverse=True)
batch=[]
if eval_dirs:
    d=eval_dirs[0]
    for f in list(d.glob("FN_*.txt")) + list(d.glob("FP_*.txt")):
        kind="FN" if f.name.startswith("FN_") else "FP"
        lbl=f.stem.split("_",1)[1]
        text=f.read_text("utf-8",errors="ignore").splitlines()
        for i,ln in enumerate(text):
            t=ln.strip()
            if not t: continue
            if t in ds_text:  # 已在資料集中，略過
                continue
            batch.append({"src":kind, "suggested_label": lbl if lbl in label_set else "", "text": t})
batch = dedup_text(batch)
outdir = ROOT/f"reports_auto/labeling/{NOW}"
outdir.mkdir(parents=True, exist_ok=True)
csvp = outdir/"intent_labeling_batch.csv"
with csvp.open("w", newline="", encoding="utf-8") as w:
    wr=csv.writer(w)
    wr.writerow(["id","src","suggested_label","final_label","text"])
    for i,r in enumerate(batch,1):
        wr.writerow([f"L{i:05d}", r["src"], r["suggested_label"], "", r["text"]])
print(f"[OK] labeling batch -> {csvp.as_posix()} rows={len(batch)}")
PY
echo "[HINT] 請開啟 CSV 填入 final_label 後，再執行 scripts/sma_merge_labeled_to_dataset_v1.sh 併回資料集"

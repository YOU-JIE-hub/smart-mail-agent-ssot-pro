#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
CSV_PATH="${1:-$(ls -t reports_auto/labeling/*/intent_labeling_batch.csv 2>/dev/null | head -n1)}"
[ -f "$CSV_PATH" ] || { echo "[FATAL] 找不到標註 CSV：$CSV_PATH"; exit 2; }
python - <<'PY'
# -*- coding: utf-8 -*-
import csv, json, time
from pathlib import Path
ROOT=Path(".")
CSV=Path("${CSV_PATH}")
ALLOW={"報價","技術支援","投訴","規則詢問","資料異動","其他"}
def read_jsonl(p):
    out=[]; 
    if not p.exists() or p.stat().st_size==0: return out
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if ln: out.append(json.loads(ln))
    return out
ds_p = ROOT/"data/intent_eval/dataset.jsonl"
clean_p = ROOT/"data/intent_eval/dataset.cleaned.jsonl"
ds = read_jsonl(ds_p)
clean = read_jsonl(clean_p) if clean_p.exists() else ds[:]
ds_text=set((r.get("text","") or "").strip() for r in ds)
added=0; new=[]
with CSV.open("r", encoding="utf-8") as f:
    for i,row in enumerate(csv.DictReader(f),1):
        final=row.get("final_label","").strip()
        text=(row.get("text","") or "").strip()
        if not final or final not in ALLOW: continue
        if not text or text in ds_text: continue
        rec={"label": final, "text": text}
        new.append(rec); ds_text.add(text); added+=1
if new:
    ds.extend(new)
    ds_p.write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in ds), "utf-8")
    clean.extend(new)
    clean_p.write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in clean), "utf-8")
print(f"[OK] merged labeled -> +{added}, dataset size={len(ds)}, cleaned size={len(clean)}")
PY

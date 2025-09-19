#!/usr/bin/env python3
import json, glob, os
from pathlib import Path
import numpy as np

ROOT=Path("/home/youjie/projects/smart-mail-agent_ssot")
# 最新 intent 評估
cands=[]
for m in glob.glob(str(ROOT/"reports_auto/eval/*/metrics.json")):
    j=json.load(open(m,"r",encoding="utf-8"))
    if j.get("dataset_size",0)>1:
        cands.append(os.path.dirname(m))
cands.sort()
INTENT_DIR=cands[-1]

th=json.load(open(ROOT/"reports_auto/intent_thresholds.json","r",encoding="utf-8"))
ds=[json.loads(x) for x in open(ROOT/"data/intent_eval/dataset.jsonl","r",encoding="utf-8")]
pr=[json.loads(x) for x in open(os.path.join(INTENT_DIR,"eval_pred.jsonl"),"r",encoding="utf-8")]

gold=[d["intent"] for d in ds]
pred=[]
for d,p in zip(ds,pr):
    lab=p["pred_intent"]; conf=p.get("intent_conf",0.0)
    pred.append(lab if conf>=th.get(lab,th.get("其他",0.40)) else "其他")

labels=sorted(set(gold)|set(pred))
def prf(lbl):
    tp=sum(1 for g,y in zip(gold,pred) if g==lbl and y==lbl)
    fp=sum(1 for g,y in zip(gold,pred) if g!=lbl and y==lbl)
    fn=sum(1 for g,y in zip(gold,pred) if g==lbl and y!=lbl)
    P=tp/(tp+fp) if tp+fp>0 else 0.0
    R=tp/(tp+fn) if tp+fn>0 else 0.0
    F=2*P*R/(P+R) if P+R>0 else 0.0
    return P,R,F
rows=[]
for L in labels:
    P,R,F = prf(L)
    rows.append((L, round(P,3), round(R,3), round(F,3)))
macroF = round(sum(r[3] for r in rows)/len(rows), 3)

# 寫入補充報告
out = Path(INTENT_DIR)/"metrics_after_threshold.md"
with open(out,"w",encoding="utf-8") as f:
    f.write("# Intent metrics (after threshold routing)\n")
    f.write(f"- thresholds: {json.dumps(th,ensure_ascii=False)}\n")
    f.write(f"- macro_f1_after_threshold: {macroF}\n\n")
    f.write("|label|P|R|F1|\n|---|---:|---:|---:|\n")
    for L,P,R,F in rows:
        f.write(f"|{L}|{P}|{R}|{F}|\n")
print("[OK] write", out)

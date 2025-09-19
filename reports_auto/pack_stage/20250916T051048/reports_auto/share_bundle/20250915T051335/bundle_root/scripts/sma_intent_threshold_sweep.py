#!/usr/bin/env python3
import json, glob, os
from pathlib import Path
import numpy as np

ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot")
# 找出最新且 dataset_size>1 的 intent 評估
cands=[]
for m in glob.glob(str(ROOT/"reports_auto/eval/*/metrics.json")):
    j=json.load(open(m,"r",encoding="utf-8"))
    if j.get("dataset_size",0)>1:
        cands.append((os.path.dirname(m), j.get("dataset_size")))
cands.sort()
if not cands: raise SystemExit("[FATAL] 找不到評估資料夾")
INTENT_DIR = cands[-1][0]

ds=[json.loads(x) for x in open(ROOT/"data/intent_eval/dataset.jsonl","r",encoding="utf-8")]
pr=[json.loads(x) for x in open(os.path.join(INTENT_DIR,"eval_pred.jsonl"),"r",encoding="utf-8")]

labels = sorted(set(d["intent"] for d in ds) | set(p["pred_intent"] for p in pr))
# 由預測中每類的信心值形成掃描點
per_class_scores = {lab:[] for lab in labels}
for d,p in zip(ds,pr):
    per_class_scores[p["pred_intent"]].append(p.get("intent_conf",0.0))

def macro_f1_after_threshold(th_map):
    gold=[d["intent"] for d in ds]
    pred=[]
    for d,p in zip(ds,pr):
        pred_lab=p["pred_intent"]; conf=p.get("intent_conf",0.0)
        thr = th_map.get(pred_lab, th_map.get("其他",0.40))
        pred.append(pred_lab if conf>=thr else "其他")
    all_labels=sorted(set(gold)|set(pred))
    def f1(lbl):
        tp=sum(1 for g,y in zip(gold,pred) if g==lbl and y==lbl)
        fp=sum(1 for g,y in zip(gold,pred) if g!=lbl and y==lbl)
        fn=sum(1 for g,y in zip(gold,pred) if g==lbl and y!=lbl)
        prec=tp/(tp+fp) if tp+fp>0 else 0.0
        rec =tp/(tp+fn) if tp+fn>0 else 0.0
        return (2*prec*rec/(prec+rec)) if (prec+rec)>0 else 0.0
    f1s=[f1(l) for l in all_labels]
    return float(np.mean(f1s))

# 掃 0.30~0.90（步長 0.01）
grid = [round(x,2) for x in np.linspace(0.30,0.90,61)]
best_map = {}
per_class_best = {}
for lab in labels:
    if lab=="其他":
        per_class_best[lab] = 0.40
        continue
    best=(0.0, 0.50)  # (score, thr)
    for t in grid:
        trial = {k:(0.40 if k=="其他" else 0.55) for k in labels}
        trial[lab]=t
        score = macro_f1_after_threshold(trial)
        if score > best[0]: best=(score, t)
    per_class_best[lab]=best[1]
# 其他維持 0.40
per_class_best["其他"]=0.40

# 重新計算最終 macro_f1_after_threshold
final_f1 = macro_f1_after_threshold(per_class_best)

# 寫入檔案
out_thr = ROOT/"reports_auto/intent_thresholds.json"
out_thr.write_text(json.dumps(per_class_best,ensure_ascii=False,indent=2),encoding="utf-8")
md = Path(INTENT_DIR)/"threshold_sweep.md"
md.write_text(
    "# Intent Threshold Sweep\n"
    f"- eval_dir: {INTENT_DIR}\n"
    f"- thresholds: {json.dumps(per_class_best,ensure_ascii=False)}\n"
    f"- macro_f1_after_threshold: {round(final_f1,3)}\n",
    encoding="utf-8"
)
print("[OK] thresholds ->", out_thr)
print("[OK] report    ->", md)

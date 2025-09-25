#!/usr/bin/env python3
import os, json, time
from pathlib import Path
ROOT=Path(os.getcwd()); PRO=ROOT/"reports_auto"/"pro"/"latest"
S=json.loads((PRO/"summary.json").read_text(encoding="utf-8"))
def find_rec():
    tsv=PRO/"threshold_sweep.tsv"
    if not tsv.exists(): return None
    lines=tsv.read_text(encoding="utf-8").splitlines()
    for i,line in enumerate(lines[1:], start=2):
        p=line.split("\t"); 
        if len(p)>=2:
            try:
                if float(p[1])>=0.98: return (p[0], i)
            except: pass
    return None
rec=find_rec(); now=time.strftime("%Y-%m-%d %H:%M:%S")
md=[]
md.append(f"# Pro Evaluation Summary @ {now}\n\n")
md.append("## Overview\n\n")
md.append(f"- Samples — Intent: **{S['metrics']['intent']['n']}**, Spam: **{S['metrics']['spam']['n']}**\n")
md.append(f"- Intent — Accuracy: **{S['metrics']['intent']['accuracy']:.4f}**, Macro-F1: **{S['metrics']['intent']['macro_f1']:.4f}**\n")
md.append(f"- Spam   — Accuracy: **{S['metrics']['spam']['accuracy']:.4f}**, Macro-F1: **{S['metrics']['spam']['macro_f1']:.4f}**\n\n")
md.append("## Spam Threshold Recommendation\n\n")
if rec:
    t,line_no=rec
    md.append(f"- **Recommended threshold**: `t = {t}` （來源：`threshold_sweep.tsv` 第 **{line_no}** 行，規則：precision ≥ 0.98 的最小 t）\n\n")
else:
    rt=S['metrics']['spam']['recommended_threshold_precision>=0.98']
    md.append(f"- **Recommended threshold**: {'N/A' if rt is None else f't = {rt}'}\n\n")
md.append("## Confusion Matrix (Intent)\n\n見 `confusion_matrix.tsv`\n\n")
md.append("## Top Errors (Spam)\n\n見 `errors_top.tsv`\n\n")
md.append("## Provenance\n\n")
for k in ("intent_pkl","spam_pkl","kie_dir","intent_classes_json"):
    v=S.get("provenance",{}).get(k) or {}
    line=f"- **{k}** — exists={v.get('exists')}, kind={v.get('kind','?')}, path=`{v.get('path','')}`"
    if v.get("kind")=="file": line+=f", size={v.get('size','?')}, sha256(head16MB)=`{v.get('sha256_head16mb','-')}`"
    md.append(line+"\n")
(PRO/"summary.md").write_text("".join(md),encoding="utf-8")
print(PRO)

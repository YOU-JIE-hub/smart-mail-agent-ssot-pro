#!/usr/bin/env python3
import json, sys
from pathlib import Path
from collections import defaultdict, deque

def iou(a,b):
    s=max(a["start"], b["start"]); e=min(a["end"], b["end"])
    inter=max(0, e-s)
    union=max(a["end"], b["end"]) - min(a["start"], b["start"])
    return inter/union if union>0 else 0.0

def load_rows(p):
    occ=defaultdict(int); rows=[]
    with open(p,encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln); t=o["text"]
            k=(t,occ[t]); occ[t]+=1
            rows.append((k,t,o.get("spans",[])))
    return rows

pred_path = sys.argv[1] if len(sys.argv)>1 else "reports_auto/kie_pred.jsonl"
gold_path = sys.argv[2] if len(sys.argv)>2 else "data/kie/test.jsonl"
out_tsv   = sys.argv[3] if len(sys.argv)>3 else "reports_auto/kie_errors.tsv"
out_sum   = "reports_auto/kie_error_summary.txt"

P=load_rows(pred_path); G=load_rows(gold_path)
gmap=defaultdict(deque); 
for k,t,sp in G: gmap[k].append((t,sp))

rows=[]
sumcnt=defaultdict(int)

for k,t,ps in P:
    if not gmap[k]:
        rows.append(("unaligned_pred","","",t,"",""))
        sumcnt["unaligned_pred"]+=1
        continue
    gt,gold = gmap[k].popleft()
    # 匹配
    used=set()
    # 先找 IoU>=0.5
    for i,pg in enumerate(ps):
        best=None; best_j=-1; best_idx=-1
        for j,gg in enumerate(gold):
            jacc=iou(pg,gg)
            if jacc>best_j:
                best, best_j, best_idx = gg, jacc, j
        if best_j<=0:
            rows.append(("spurious", pg["label"],"", t, f'{pg["start"]}-{pg["end"]}', ""))
            sumcnt["spurious"]+=1
        else:
            used.add(best_idx)
            if pg["label"]!=best["label"] and best_j>=0.5:
                rows.append(("type_error", pg["label"],best["label"], t, f'{pg["start"]}-{pg["end"]}', f'{best["start"]}-{best["end"]}'))
                sumcnt[f"type_error:{best['label']}"]+=1
            elif pg["label"]==best["label"] and best_j<1.0 and best_j>=0.5:
                rows.append(("boundary", pg["label"],pg["label"], t, f'{pg["start"]}-{pg["end"]}', f'{best["start"]}-{best["end"]}'))
                sumcnt[f"boundary:{pg['label']}"]+=1
    # 遺漏
    for j,gg in enumerate(gold):
        if j not in used:
            rows.append(("missing","",gg["label"], t, "", f'{gg["start"]}-{gg["end"]}'))
            sumcnt[f"missing:{gg['label']}"]+=1

Path(out_tsv).write_text(
    "type\tpred_label\tgold_label\ttext\tpred_span\tgold_span\n" + 
    "\n".join("\t".join(map(str,r)) for r in rows[:200]), encoding="utf-8"
)
Path(out_sum).write_text(
    "\n".join(f"{k}\t{v}" for k,v in sorted(sumcnt.items())), encoding="utf-8"
)
print("[OK] ->", out_tsv, "and", out_sum)

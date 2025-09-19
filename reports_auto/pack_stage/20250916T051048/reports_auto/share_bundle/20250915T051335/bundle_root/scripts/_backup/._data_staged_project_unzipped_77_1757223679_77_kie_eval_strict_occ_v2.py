#!/usr/bin/env python3
import json, sys
from collections import defaultdict, deque
from pathlib import Path

pred_path = sys.argv[1] if len(sys.argv)>1 else "reports_auto/kie_pred.jsonl"
gold_path = sys.argv[2] if len(sys.argv)>2 else "data/kie/test.jsonl"
out_path  = sys.argv[3] if len(sys.argv)>3 else "reports_auto/kie_eval.txt"

def load_occ_list(p):
    occ = defaultdict(int); rows=[]
    with open(p,encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln); t=o["text"]; k=(t,occ[t]); occ[t]+=1
            spans=[(s["start"],s["end"],s["label"]) for s in o.get("spans",[])]
            rows.append((k,set(spans), len(spans)))
    return rows  # list of ((text,idx), span_set, span_count)

P = load_occ_list(pred_path)
G = load_occ_list(gold_path)

gmap = defaultdict(deque)
for k,sp,c in G: gmap[k].append((sp,c))

tp=fp=fn=0
aligned=0
miss_from_pred=0  # gold多出
miss_from_gold=0  # pred多出
fp_extra=0  # 來自 pred-only 行的假陽性 span 數
fn_missing=0  # 來自 gold-only 行的假陰性 span 數

for k,ps,pcnt in P:
    if gmap[k]:
        gs,gcnt = gmap[k].popleft()
        tp += len(ps & gs)
        fp += len(ps - gs)
        fn += len(gs - ps)
        aligned += 1
    else:
        miss_from_gold += 1
        fp_extra += pcnt

for k,rest in gmap.items():
    for gs,gcnt in rest:
        miss_from_pred += 1
        fn_missing += gcnt

# 懲罰：把未對齊行的 span 也納入
fp_total = fp + fp_extra
fn_total = fn + fn_missing

prec = tp/(tp+fp_total) if tp+fp_total else 0.0
rec  = tp/(tp+fn_total) if tp+fn_total else 0.0
f1   = 2*prec*rec/(prec+rec) if prec+rec else 0.0

Path(out_path).write_text(
    "pred_rows={}\ngold_rows={}\naligned_rows={}\n"
    "miss_from_pred={}  # gold多出、pred缺少的出現次數\n"
    "miss_from_gold={}  # pred多出、gold缺少的出現次數\n"
    "raw_tp={} raw_fp={} raw_fn={}\n"
    "penalty_fp_extra={} penalty_fn_missing={}\n"
    "effective_fp={} effective_fn={}\n"
    "strict_span_P={:.4f}\nstrict_span_R={:.4f}\nstrict_span_F1={:.4f}\n"
    .format(len(P), len(G), aligned,
            miss_from_pred, miss_from_gold,
            tp, fp, fn, fp_extra, fn_missing, fp_total, fn_total,
            prec, rec, f1),
    encoding="utf-8"
)
print("[OK] ->", out_path)

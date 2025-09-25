import json, sys
from collections import defaultdict
from pathlib import Path

pred_path = sys.argv[1] if len(sys.argv)>1 else "reports_auto/kie_pred.jsonl"
gold_path = sys.argv[2] if len(sys.argv)>2 else "data/kie/test.jsonl"
out_path  = sys.argv[3] if len(sys.argv)>3 else "reports_auto/kie_eval.txt"

def load_occ_list(p):
    occ = defaultdict(int)
    rows = []
    with open(p,encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln); t=o["text"]
            k=(t, occ[t]); occ[t]+=1
            spans=set((s["start"],s["end"],s["label"]) for s in o.get("spans",[]))
            rows.append((k, spans))
    return rows  # list of ((text,occ_idx), span_set)

P = load_occ_list(pred_path)
G = load_occ_list(gold_path)

# 建立 gold 的索引: key -> list of span_set（按出現次序）
from collections import defaultdict, deque
gmap = defaultdict(deque)
for k,sp in G: gmap[k].append(sp)

tp=fp=fn=0
aligned=0
miss_from_pred=0
miss_from_gold=0

for k,ps in P:
    if gmap[k]:
        gs = gmap[k].popleft()
        tp += len(ps & gs)
        fp += len(ps - gs)
        fn += len(gs - ps)
        aligned += 1
    else:
        # pred 有但 gold 沒對應出現次序
        miss_from_gold += 1

# 剩下 gold 未配對
for k,rest in gmap.items():
    miss_from_pred += len(rest)

prec = tp/(tp+fp) if tp+fp else 0.0
rec  = tp/(tp+fn) if tp+fn else 0.0
f1   = 2*prec*rec/(prec+rec) if prec+rec else 0.0

Path(out_path).write_text(
    "pred_rows={}\ngold_rows={}\naligned_rows={}\n"
    "miss_from_pred={}  # gold多出、pred缺少的出現次數\n"
    "miss_from_gold={}  # pred多出、gold缺少的出現次數\n"
    "strict_span_P={:.4f}\nstrict_span_R={:.4f}\nstrict_span_F1={:.4f}\n"
    .format(len(P), len(G), aligned, miss_from_pred, miss_from_gold, prec, rec, f1),
    encoding="utf-8"
)
print("[OK] ->", out_path)

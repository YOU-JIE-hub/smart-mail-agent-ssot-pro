import json, sys
from pathlib import Path

pred_path = sys.argv[1] if len(sys.argv)>1 else "reports_auto/kie_pred.jsonl"
gold_path = sys.argv[2] if len(sys.argv)>2 else "data/kie/test.jsonl"
out_path  = sys.argv[3] if len(sys.argv)>3 else "reports_auto/kie_eval.txt"

def load_map(p):
    m={}
    with open(p,encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln); m[o["text"]]=set((s["start"],s["end"],s["label"]) for s in o.get("spans",[]))
    return m

P=load_map(pred_path); G=load_map(gold_path)
keys = sorted(set(P).intersection(G))
miss_pred = sorted(set(G).difference(P))
miss_gold = sorted(set(P).difference(G))

tp=fp=fn=0
for t in keys:
    Ps=P[t]; Gs=G[t]
    tp+=len(Ps & Gs); fp+=len(Ps - Gs); fn+=len(Gs - Ps)

prec=tp/(tp+fp) if tp+fp else 0.0
rec =tp/(tp+fn) if tp+fn else 0.0
f1  =2*prec*rec/(prec+rec) if prec+rec else 0.0

Path(out_path).write_text(
    "aligned_lines={}\nmiss_from_pred={}\nmiss_from_gold={}\n"
    "strict_span_P={:.4f}\nstrict_span_R={:.4f}\nstrict_span_F1={:.4f}\n"
    .format(len(keys), len(miss_pred), len(miss_gold), prec, rec, f1),
    encoding="utf-8")
print("[OK] ->", out_path)

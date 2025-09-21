#!/usr/bin/env python3
import json, argparse
from pathlib import Path
from sklearn.metrics import f1_score, precision_recall_fscore_support, roc_auc_score, average_precision_score

def load_gold(p):
    G={}
    for ln in open(p,encoding="utf-8",errors="ignore"):
        if not ln.strip(): continue
        o=json.loads(ln)
        if "is_spam" in o: G[o["id"]] = int(o["is_spam"])
        elif "label" in o: G[o["id"]] = 1 if str(o["label"]).lower()=="spam" else 0
    return G

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--out",  required=True)
    ap.add_argument("--grid", default="0.10,0.20,0.30,0.40,0.50,0.60,0.70,0.80,0.90")
    args=ap.parse_args()

    G=load_gold(args.gold)
    P=[json.loads(x) for x in open(args.pred,encoding="utf-8",errors="ignore") if x.strip()]
    ids=set(G).intersection({o["id"] for o in P})
    if not ids:
        Path(args.out).write_text(json.dumps({"score_threshold":0.5})+"\n",encoding="utf-8")
        print("[WARN] no overlap -> default 0.5")
        return
    scores={o["id"]: float((o.get("spam") or {}).get("score_text",0.0)) for o in P if o["id"] in ids}
    rules ={o["id"]: int((o.get("spam") or {}).get("pred_rule",0)) for o in P if o["id"] in ids}
    y_true=[G[i] for i in ids]

    best=(None,-1.0)  # thr, f1
    for t in [float(x) for x in args.grid.split(",")]:
        y_text=[1 if scores[i]>=t else 0 for i in ids]
        y_pred=[1 if (rules[i] or y_text[j]) else 0 for j,i in enumerate(ids)]
        f1=f1_score(y_true,y_pred,zero_division=0)
        if f1>best[1]: best=(t,f1)
    thr,f1=best
    # 附帶 AUC（用 score_text）
    try:
        roc=roc_auc_score(y_true,[scores[i] for i in ids])
        pr =average_precision_score(y_true,[scores[i] for i in ids])
    except Exception:
        roc=pr=0.0
    Path(args.out).write_text(json.dumps({"score_threshold":thr,"dev_F1":f1,"roc_auc":roc,"pr_auc":pr},ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"[BEST] Spam thr={thr} F1={f1:.4f} ROC-AUC={roc:.4f} PR-AUC={pr:.4f} -> {args.out}")
if __name__=="__main__": main()

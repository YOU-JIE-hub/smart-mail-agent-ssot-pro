#!/usr/bin/env python3
import json, argparse
from pathlib import Path
from sklearn.metrics import f1_score

def load_jsonl(p): 
    for ln in open(p,encoding="utf-8",errors="ignore"):
        if ln.strip(): yield json.loads(ln)

def decide(c1, p1, p2, has_other, p1_thr, margin, lock=True):
    # policy_qa lock：若 top1 是 policy_qa 且 p1>=thr，忽略 margin
    if c1=="policy_qa" and lock and (p1>=p1_thr): 
        return c1
    ok = (p1>=p1_thr) and ((p1-p2)>=margin)
    return c1 if ok else ("other" if has_other else c1)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--out",  required=True)
    ap.add_argument("--grid_p1", default="0.30,0.40,0.50,0.60,0.70")
    ap.add_argument("--grid_margin", default="0.00,0.05,0.08,0.10,0.15")
    args=ap.parse_args()

    G={o["id"]:o["label"] for o in (json.loads(x) for x in open(args.gold,encoding="utf-8")) if o.get("id")}
    R=list(load_jsonl(args.pred))
    ids=set(G).intersection({r["id"] for r in R})
    if not ids: 
        print("[WARN] no overlap between gold and pred"); 
        open(args.out,"w").write(json.dumps({"p1":0.5,"margin":0.08,"policy_lock":True})+"\n"); 
        return
    has_other = True  # 你的類別含 other

    grid_p1=[float(x) for x in args.grid_p1.split(",")]
    grid_margin=[float(x) for x in args.grid_margin.split(",")]

    best=(None,None,-1.0)  # p1, margin, f1
    for p1_thr in grid_p1:
        for mg in grid_margin:
            y_true=[]; y_pred=[]
            for r in R:
                i=r["id"]
                if i not in ids: continue
                it=r.get("intent") or {}
                y_true.append(G[i])
                y_pred.append(decide(it.get("base_top1"), float(it.get("p1",0)), float(it.get("p2",0)), has_other, p1_thr, mg))
            f1=f1_score(y_true,y_pred,average="macro", zero_division=0)
            if f1>best[2]: best=(p1_thr,mg,f1)
    p1_thr,mg,f1=best
    obj={"p1":p1_thr,"margin":mg,"policy_lock":True,"dev_macroF1":f1}
    Path(args.out).write_text(json.dumps(obj,ensure_ascii=False)+"\n", encoding="utf-8")
    print(f"[BEST] Intent p1={p1_thr} margin={mg} macroF1={f1:.4f} -> {args.out}")
if __name__=="__main__": main()

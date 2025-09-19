#!/usr/bin/env python3
import json, argparse
from pathlib import Path
def decide(c1,p1,p2,has_other,p1_thr,margin,lock=True):
    if c1=="policy_qa" and lock and (p1>=p1_thr): return c1
    ok=(p1>=p1_thr) and ((p1-p2)>=margin)
    return c1 if ok else ("other" if has_other else c1)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in_pred", required=True)
    ap.add_argument("--out_pred", required=True)
    ap.add_argument("--thr", required=True) # json: {p1, margin, policy_lock}
    args=ap.parse_args()
    t=json.loads(Path(args.thr).read_text(encoding="utf-8"))
    p1_thr=float(t.get("p1",0.5)); margin=float(t.get("margin",0.08)); lock=bool(t.get("policy_lock",True))
    has_other=True
    with open(args.in_pred,encoding="utf-8",errors="ignore") as fi, open(args.out_pred,"w",encoding="utf-8") as fo:
        for ln in fi:
            if not ln.strip(): continue
            o=json.loads(ln)
            it=o.get("intent") or {}
            c1,p1,p2=it.get("base_top1"), float(it.get("p1",0)), float(it.get("p2",0))
            it["tuned"]=decide(c1,p1,p2,has_other,p1_thr,margin,lock)
            o["intent"]=it
            fo.write(json.dumps(o,ensure_ascii=False)+"\n")
    print(f"[APPLIED] intent thresholds -> {args.out_pred}")
if __name__=="__main__": main()

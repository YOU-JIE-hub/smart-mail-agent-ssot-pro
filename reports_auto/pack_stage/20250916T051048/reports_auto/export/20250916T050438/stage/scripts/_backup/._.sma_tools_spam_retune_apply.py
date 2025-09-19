#!/usr/bin/env python3
import json, argparse
from pathlib import Path
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in_pred", required=True)
    ap.add_argument("--out_pred", required=True)
    ap.add_argument("--thr", required=True) # json: {score_threshold}
    args=ap.parse_args()
    t=json.loads(Path(args.thr).read_text(encoding="utf-8"))
    thr=float(t.get("score_threshold",0.5))
    with open(args.in_pred,encoding="utf-8",errors="ignore") as fi, open(args.out_pred,"w",encoding="utf-8") as fo:
        for ln in fi:
            if not ln.strip(): continue
            o=json.loads(ln)
            sp=o.get("spam") or {}
            score=float(sp.get("score_text",0.0))
            pred_text=int(score>=thr)
            pred_rule=int(sp.get("pred_rule",0))
            sp["pred_text"]=pred_text
            sp["pred_ens"]=1 if (pred_text or pred_rule) else 0
            o["spam"]=sp
            fo.write(json.dumps(o,ensure_ascii=False)+"\n")
    print(f"[APPLIED] spam threshold -> {args.out_pred}")
if __name__=="__main__": main()

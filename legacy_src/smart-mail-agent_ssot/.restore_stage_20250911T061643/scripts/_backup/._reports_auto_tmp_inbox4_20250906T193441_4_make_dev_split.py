#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, argparse, random
from pathlib import Path
from collections import defaultdict, Counter

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out_dir", default="data/intent")
    ap.add_argument("--valid_ratio", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args=ap.parse_args()

    rng = random.Random(args.seed)
    rows=[]
    with open(args.src,"r",encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln); y=o.get("label") or o.get("intent") or o.get("y")
            t=o.get("text") or (o.get("subject","")+"\n"+o.get("body",""))
            if y and t: rows.append(o)

    by=defaultdict(list)
    for o in rows: by[o.get("label") or o.get("intent") or o.get("y")].append(o)

    train, valid = [], []
    for lab, lst in by.items():
        rng.shuffle(lst)
        k = max(1, int(len(lst)*args.valid_ratio))
        valid.extend(lst[:k]); train.extend(lst[k:])

    outdir = Path(args.out_dir); outdir.mkdir(parents=True, exist_ok=True)
    p_tr=outdir/"dev_train.jsonl"; p_va=outdir/"dev_valid.jsonl"
    with open(p_tr,"w",encoding="utf-8") as f:
        for o in train: f.write(json.dumps(o, ensure_ascii=False)+"\n")
    with open(p_va,"w",encoding="utf-8") as f:
        for o in valid: f.write(json.dumps(o, ensure_ascii=False)+"\n")

    print("[TRAIN]", p_tr, Counter(o['label'] for o in train))
    print("[VALID]", p_va, Counter(o['label'] for o in valid))

if __name__ == "__main__":
    main()

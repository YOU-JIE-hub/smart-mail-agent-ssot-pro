#!/usr/bin/env python3
import argparse, json, random
from pathlib import Path
R=random.Random(42)
def stratified_sample(rows, key, ratio):
    from collections import defaultdict
    buckets=defaultdict(list)
    for i,r in enumerate(rows): buckets[r.get(key,"other")].append((i,r))
    pick=[]
    for lab,items in buckets.items():
        k=max(1,int(len(items)*ratio))
        pick+=R.sample(items,k=min(k,len(items)))
    pick.sort(key=lambda x:x[0]); return [r for _,r in pick]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in_jsonl", required=True, help="train_aug.jsonl")
    ap.add_argument("--out_jsonl", default="data/kie/label_queue.jsonl")
    ap.add_argument("--ratio", type=float, default=0.25)
    args=ap.parse_args()
    rows=[json.loads(l) for l in Path(args.in_jsonl).open(encoding="utf-8")]
    sel=stratified_sample(rows, key="label", ratio=args.ratio)
    Path(args.out_jsonl).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.out_jsonl).open("w",encoding="utf-8") as f:
        for r in sel: f.write(json.dumps({"text":r["text"]},ensure_ascii=False)+"\n")
    print(f"[QUEUE] wrote={len(sel)} -> {args.out_jsonl}")
if __name__=="__main__": main()

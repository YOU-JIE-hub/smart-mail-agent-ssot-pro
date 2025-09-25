#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path
def sha(p): 
    h=hashlib.sha256(); 
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1<<20), b""): h.update(b)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--train", default="data/intent/train_aug.jsonl")
    ap.add_argument("--val",   default="data/intent/val_aug.jsonl")
    ap.add_argument("--test",  default="data/intent/test.jsonl")
    ap.add_argument("--rules", default=".sma_tools/ruleset.yml")
    ap.add_argument("--out",   default="reports_auto/dataset_manifest.json")
    a=ap.parse_args()
    obj={"train":sha(a.train),"val":sha(a.val),"test":sha(a.test),"rules":sha(a.rules)}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding="utf-8")
    print("[MANIFEST] ->", a.out); print(json.dumps(obj, ensure_ascii=False))
if __name__=="__main__": main()

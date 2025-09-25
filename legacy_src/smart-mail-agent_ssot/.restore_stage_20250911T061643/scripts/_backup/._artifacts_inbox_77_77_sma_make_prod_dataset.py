#!/usr/bin/env python3
from __future__ import annotations
import json, argparse
from pathlib import Path
SETS=[("trec06c_zip","data/trec06c_zip"),
      ("spam_sa","data/spam_sa"),
      ("spam_synth","data/spam")]
def cat_to(dst, parts):
    with open(dst,"w",encoding="utf-8") as w:
        for fp in parts:
            if not Path(fp).exists(): continue
            for line in open(fp,encoding="utf-8"):
                e=json.loads(line); e["__domain__"]=Path(fp).parts[-2]  # 記錄來源資料夾
                w.write(json.dumps(e,ensure_ascii=False)+"\n")
def count(fp):
    n=h=s=0
    if not Path(fp).exists(): return 0,0,0
    for line in open(fp,encoding="utf-8"):
        n+=1; e=json.loads(line); (h,s)=(h+ (e["label"]=="ham"), s+ (e["label"]=="spam"))
    return n,h,s
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="data/prod_merged")
    a=ap.parse_args()
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    train_parts=[]; val_parts=[]; test_parts=[]
    for name,root in SETS:
        if all((Path(root)/x).exists() for x in ("train.jsonl","val.jsonl","test.jsonl")):
            train_parts.append(f"{root}/train.jsonl")
            val_parts.append(f"{root}/val.jsonl")
            test_parts.append(f"{root}/test.jsonl")
            print(f"[USE] {name}")
        else:
            print(f"[SKIP] {name} (missing files)")
    cat_to(out/"train.jsonl", train_parts)
    cat_to(out/"val.jsonl",   val_parts)
    cat_to(out/"test.jsonl",  test_parts)
    for split in ("train","val","test"):
        n,h,s=count(out/f"{split}.jsonl")
        print(f"[MERGED] {split}: N={n} ham={h} spam={s} -> {out}/{split}.jsonl")

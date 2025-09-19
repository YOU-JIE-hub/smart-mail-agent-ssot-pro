#!/usr/bin/env python3
from __future__ import annotations
import json, random, sys
from pathlib import Path

random.seed(20250901)
def read_jsonl(p:Path):
    if not p.exists(): return []
    with p.open(encoding="utf-8") as f: return [json.loads(x) for x in f]

def write_jsonl(rows, p:Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w",encoding="utf-8") as w:
        for r in rows: w.write(json.dumps(r, ensure_ascii=False)+"\n")

def stratify(rows, ratio=(0.70,0.15,0.15)):
    by={"ham":[],"spam":[]}
    for e in rows: by[e["label"]].append(e)
    out={"train":[], "val":[], "test":[]}
    for lbl, arr in by.items():
        random.shuffle(arr)
        n=len(arr); n_tr=int(ratio[0]*n); n_val=int(ratio[1]*n)
        out["train"]+=arr[:n_tr]
        out["val"]  +=arr[n_tr:n_tr+n_val]
        out["test"] +=arr[n_tr+n_val:]
    for k in out: random.shuffle(out[k])
    return out

def coalesce_one(root:Path, tag:str):
    # 優先使用已切好的 train/val/test；沒有就用 all.jsonl 再分
    parts={}
    for split in ("train","val","test"):
        fp=root/f"{split}.jsonl"
        parts[split]=read_jsonl(fp)
    if not any(parts.values()):
        allp=root/"all.jsonl"
        if allp.exists():
            sp=stratify(read_jsonl(allp))
            parts=sp
    # id 去重 + 加上來源前綴
    for k,arr in parts.items():
        uniq=[]; seen=set()
        for i,e in enumerate(arr):
            eid=f"{tag}::{e.get('id', i)}"
            if eid in seen: continue
            e=dict(e); e["id"]=eid; uniq.append(e); seen.add(eid)
        parts[k]=uniq
    return parts

roots=[]
for d in ("data/trec06c_zip","data/spam_sa","data/spam"):
    rp=Path(d)
    if (rp.exists() and any((rp/f).exists() for f in ("train.jsonl","val.jsonl","test.jsonl","all.jsonl"))):
        print(f"[USE] {rp.name}"); roots.append((rp, rp.name.replace("data/","").replace("/","_")))
if not roots:
    print("[FATAL] 找不到可用資料（data/trec06c_zip 或 data/spam_sa 或 data/spam）", file=sys.stderr); sys.exit(2)

merged={"train":[], "val":[], "test":[]}
for rp,tag in roots:
    parts=coalesce_one(rp, tag)
    for k in merged: merged[k]+=parts.get(k,[])
# 最後再洗牌
for k in merged:
    random.shuffle(merged[k])
    write_jsonl(merged[k], Path("data/prod_merged")/f"{k}.jsonl")

def cnt(rows): 
    h=sum(1 for r in rows if r["label"]=="ham")
    s=sum(1 for r in rows if r["label"]=="spam")
    return len(rows),h,s

for k in ("train","val","test"):
    n,h,s=cnt(merged[k])
    print(f"[MERGED] {k}: N={n} ham={h} spam={s} -> data/prod_merged/{k}.jsonl")

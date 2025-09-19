#!/usr/bin/env python3
from __future__ import annotations
import json, random, sys
from pathlib import Path

src = Path("data/benchmarks/spamassassin.jsonl")
out_dir = Path("data/spam_sa"); out_dir.mkdir(parents=True, exist_ok=True)
random.seed(20250830)

rows = [json.loads(x) for x in open(src,encoding="utf-8")]
by_lbl = {"ham":[], "spam":[]}
for e in rows:
    by_lbl[e["label"]].append(e)

def split(arr):
    n=len(arr); idx=list(range(n)); random.shuffle(idx)
    n_train=int(0.70*n); n_val=int(0.15*n)
    train=[arr[i] for i in idx[:n_train]]
    val  =[arr[i] for i in idx[n_train:n_train+n_val]]
    test =[arr[i] for i in idx[n_train+n_val:]]
    return train,val,test

th,tv,tt = split(by_lbl["ham"])
sh,sv,st = split(by_lbl["spam"])
train = th+sh; val = tv+sv; test = tt+st

def dump(path, items):
    with open(path,"w",encoding="utf-8") as w:
        for e in items: w.write(json.dumps(e,ensure_ascii=False)+"\n")

dump(out_dir/"train.jsonl", train)
dump(out_dir/"val.jsonl",   val)
dump(out_dir/"test.jsonl",  test)

print("[SPLIT]",
      "train=",len(train),"val=",len(val),"test=",len(test),
      "| ham(train/val/test)=",len(th),len(tv),len(tt),
      "| spam(train/val/test)=",len(sh),len(sv),len(st))

#!/usr/bin/env python3
import sys,json
from pathlib import Path
gold_in, pred_model, pred_rule, outp = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
def load(p):
  m={}
  for ln in Path(p).open(encoding='utf-8'):
    o=json.loads(ln); m.setdefault(o["text"], set())
    for s in o.get("spans",[]): m[o["text"]].add((s["start"],s["end"],s["label"]))
  return m
M=load(pred_model); R=load(pred_rule)
texts=[json.loads(x)["text"] for x in Path(gold_in).open(encoding='utf-8')]
with Path(outp).open("w",encoding="utf-8") as fo:
  for t in texts:
    S=set(); S |= M.get(t,set()); S |= R.get(t,set())
    fo.write(json.dumps({"text":t,"spans":[{"start":a,"end":b,"label":l} for a,b,l in sorted(S)]},ensure_ascii=False)+"\n")
print(f"[ENSEMBLE] -> {outp}")

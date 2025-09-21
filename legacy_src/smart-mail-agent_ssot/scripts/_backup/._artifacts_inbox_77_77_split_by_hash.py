#!/usr/bin/env python3
import sys, json, hashlib, os
src=sys.argv[1]; outdir=sys.argv[2]
os.makedirs(outdir, exist_ok=True)
fo={k:open(os.path.join(outdir,f"{k}.jsonl"),"w",encoding="utf-8") for k in ["train","val","test","blind"]}
def bucket(txt:str)->str:
    h=int(hashlib.sha256(txt.encode("utf-8")).hexdigest(),16)%10
    return "train" if h<8 else ("val" if h<9 else "test")
for ln in open(src,encoding="utf-8"):
    o=json.loads(ln); b=bucket(o.get("text",""))
    fo[b].write(json.dumps(o,ensure_ascii=False)+"\n")
    if b=="test": fo["blind"].write(json.dumps(o,ensure_ascii=False)+"\n")
for f in fo.values(): f.close()
print("[SPLIT] done:", {k:sum(1 for _ in open(os.path.join(outdir,f"{k}.jsonl"),encoding="utf-8")) for k in fo})

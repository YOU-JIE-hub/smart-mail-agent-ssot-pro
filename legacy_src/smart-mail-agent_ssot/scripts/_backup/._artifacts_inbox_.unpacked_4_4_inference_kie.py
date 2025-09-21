#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForTokenClassification
def decode(text, ids, id2, offs):
    spans=[]; cur=None
    for lab_id,(a,b) in zip(ids,offs):
        if a==b: continue
        lab=id2[lab_id]
        if lab=="O":
            if cur: spans.append(cur); cur=None
        else:
            tag,ent=lab.split("-",1)
            if tag=="B":
                if cur: spans.append(cur)
                cur={"start":a,"end":b,"label":ent}
            else:
                if cur and cur["label"]==ent: cur["end"]=b
                else: cur={"start":a,"end":b,"label":ent}
    if cur: spans.append(cur)
    return spans
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model_dir", required=True); ap.add_argument("--in_jsonl", required=True); ap.add_argument("--out_jsonl", required=True); ap.add_argument("--max_len", type=int, default=512)
    a=ap.parse_args()
    md=Path(a.model_dir); tok=AutoTokenizer.from_pretrained(md, local_files_only=bool(int(os.environ.get('SMA_LOCAL_ONLY','0')))); mdl=AutoModelForTokenClassification.from_pretrained(md, local_files_only=bool(int(os.environ.get('SMA_LOCAL_ONLY','0'))))
    import json as _json
    labels=_json.loads(Path(md,"labels.json").read_text(encoding="utf-8"))["labels"]; id2={i:l for i,l in enumerate(labels)}
    dev=torch.device("cuda" if torch.cuda.is_available() else "cpu"); mdl.to(dev).eval()
    n=0
    with Path(a.in_jsonl).open("r",encoding="utf-8") as fi, Path(a.out_jsonl).open("w",encoding="utf-8") as fo:
        for ln in fi:
            o=_json.loads(ln); t=o.get("text") or o.get("body") or ""
            enc=tok(t, return_offsets_mapping=True, truncation=True, max_length=a.max_len, return_tensors="pt")
            offs=enc.pop("offset_mapping")[0].tolist()
            with torch.no_grad(): lg=mdl(**{k:v.to(dev) for k,v in enc.items()}).logits[0]
            ids=lg.argmax(-1).cpu().tolist()
            fo.write(_json.dumps({"text":t,"spans":decode(t,ids,id2,offs)}, ensure_ascii=False)+"\n"); n+=1
    print(f"[PRED] wrote={n} -> {a.out_jsonl}")
if __name__ == "__main__": main()

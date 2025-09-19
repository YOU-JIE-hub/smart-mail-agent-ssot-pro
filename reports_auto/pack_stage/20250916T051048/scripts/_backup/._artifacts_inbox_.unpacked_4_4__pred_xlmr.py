import sys, json, torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForTokenClassification

IN=sys.argv[1]; MD=sys.argv[2]; OUT=sys.argv[3]
tok=AutoTokenizer.from_pretrained(MD, use_fast=True)
mdl=AutoModelForTokenClassification.from_pretrained(MD); mdl.eval()

def decode(text):
    enc = tok(text, return_offsets_mapping=True, truncation=True, max_length=384, return_tensors="pt")
    offs = enc.pop("offset_mapping")[0].tolist()
    with torch.no_grad():
        logits = mdl(**enc).logits[0]
    ids = logits.argmax(-1).tolist()
    id2label = mdl.config.id2label
    spans=[]; cur=None
    for i,(a,b) in enumerate(offs):
        if a==b: continue
        lab = id2label.get(ids[i],"O")
        if lab.startswith("B-"):
            if cur: spans.append(cur); cur=None
            cur={"label":lab[2:], "start":a, "end":b}
        elif lab.startswith("I-") and cur and cur["label"]==lab[2:]:
            cur["end"]=b
        else:
            if cur: spans.append(cur); cur=None
    if cur: spans.append(cur)
    return spans

n=0
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
with open(IN,encoding="utf-8") as fi, open(OUT,"w",encoding="utf-8") as fo:
    for ln in fi:
        o=json.loads(ln); t=o["text"]
        fo.write(json.dumps({"text":t,"spans":decode(t)}, ensure_ascii=False)+"\n"); n+=1
print(f"[PRED] {IN} -> {OUT} lines={n}")

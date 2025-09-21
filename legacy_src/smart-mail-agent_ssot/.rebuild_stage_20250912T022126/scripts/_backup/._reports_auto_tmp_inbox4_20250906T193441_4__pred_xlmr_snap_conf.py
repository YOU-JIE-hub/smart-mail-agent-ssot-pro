#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, re, yaml, math
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification

inp, model_dir, outp = sys.argv[1], sys.argv[2], sys.argv[3]
rules = yaml.safe_load(Path(".sma_tools/ruleset.yml").read_text(encoding="utf-8"))
thr   = yaml.safe_load(Path(".sma_tools/thresholds.yml").read_text(encoding="utf-8"))

PATS = {lab:[re.compile(rx,re.I) for rx in rules["patterns"].get(lab,[])]
        for lab in ("amount","date_time","env","sla")}

tok = AutoTokenizer.from_pretrained(model_dir, use_fast=True)
mdl = AutoModelForTokenClassification.from_pretrained(model_dir)
mdl.eval(); torch.set_grad_enabled(False)
id2label = {int(k):v for k,v in mdl.config.id2label.items()}

def decode(text:str):
    enc = tok(text, return_offsets_mapping=True, truncation=True, max_length=384, return_tensors="pt")
    offs = enc.pop("offset_mapping")[0].tolist()
    logits = mdl(**{k:v for k,v in enc.items()}).logits[0]              # [T, C]
    probs  = torch.softmax(logits, dim=-1)                               # [T, C]
    pred_i = logits.argmax(-1).tolist()                                  # [T]

    # 先 BIO 解碼
    spans=[]; cur=None; conf_tokens=[]
    for i,(a,b) in enumerate(offs):
        if a==b: continue
        lab = id2label.get(pred_i[i], "O")
        if lab.startswith("B-"):
            if cur: 
                cur["conf"]=sum(conf_tokens)/max(1,len(conf_tokens))
                spans.append(cur)
            cur={"start":a,"end":b,"label":lab[2:]}; conf_tokens=[probs[i, pred_i[i]].item()]
        elif lab.startswith("I-") and cur and cur["label"]==lab[2:]:
            cur["end"]=b; conf_tokens.append(probs[i, pred_i[i]].item())
        else:
            if cur:
                cur["conf"]=sum(conf_tokens)/max(1,len(conf_tokens))
                spans.append(cur); cur=None; conf_tokens=[]
    if cur:
        cur["conf"]=sum(conf_tokens)/max(1,len(conf_tokens))
        spans.append(cur)

    # 信心過濾
    spans=[s for s in spans if s["conf"] >= float(thr.get(s["label"], 0.5))]

    # 規則貼齊（就近最大重疊）
    snapped=[]
    for s in spans:
        best=None; best_overlap=0
        for rx in PATS.get(s["label"], []):
            for m in rx.finditer(text):
                a,b = m.start(), m.end()
                ov = max(0, min(s["end"],b)-max(s["start"],a))
                if ov>best_overlap:
                    best_overlap=ov; best=(a,b)
        if best_overlap>0:
            s["start"], s["end"] = best
        s.pop("conf", None)
        snapped.append(s)

    # 去重排序
    out=[]; seen=set()
    for s in sorted(snapped,key=lambda x:(x["start"],x["end"],x["label"])):
        k=(s["start"],s["end"],s["label"])
        if k in seen: continue
        seen.add(k); out.append(s)
    return out

with open(inp,encoding="utf-8") as fi, open(outp,"w",encoding="utf-8") as fo:
    n=0
    for ln in fi:
        o=json.loads(ln); t=o["text"]
        fo.write(json.dumps({"text":t,"spans":decode(t)},ensure_ascii=False)+"\n"); n+=1
print(f"[SNAP+CONF] {inp} -> {outp} lines={n}")

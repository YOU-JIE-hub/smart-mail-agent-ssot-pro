#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, re, yaml
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForTokenClassification
import torch
inp, model_dir, outp = sys.argv[1], sys.argv[2], sys.argv[3]
rules_path = Path(".sma_tools/ruleset.yml")
if not rules_path.exists():
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text(
        "labels: [amount, date_time, env, sla]\n"
        "patterns:\n"
        "  amount:\n"
        "    - \"(?:NT\\$|USD|US\\$|\\$|＄)\\s?[0-9０-９][0-9０-９,，]*(?:[\\.．][0-9０-９]+)?\"\n"
        "  date_time:\n"
        "    - \"\\b[12][0-9]{3}[./-][0-9]{1,2}[./-][0-9]{1,2}\\b\"\n"
        "    - \"\\b[0-9]{1,2}/[0-9]{1,2}\\b\"\n"
        "  env:\n"
        "    - \"\\b(prod|production|prd|staging|stage|stg|uat|test|dev)\\b\"\n"
        "  sla:\n"
        "    - \"\\b(SLA|RTO|RPO|EOD|EOW)\\b\"\n", encoding="utf-8")
rules = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
PATS={lab:[re.compile(rx,re.I) for rx in rules["patterns"].get(lab,[])] for lab in ("amount","date_time","env","sla")}
tok = AutoTokenizer.from_pretrained(model_dir, use_fast=True)
mdl = AutoModelForTokenClassification.from_pretrained(model_dir); mdl.eval(); torch.set_grad_enabled(False)
id2label = mdl.config.id2label
def decode(text):
    enc = tok(text, return_offsets_mapping=True, truncation=True, max_length=384, return_tensors="pt")
    offs = enc.pop("offset_mapping")[0].tolist()
    pred = mdl(**{k:v for k,v in enc.items()}).logits[0].argmax(-1).tolist()
    spans=[]; cur=None
    for i,(a,b) in enumerate(offs):
        if a==b: continue
        lab=id2label.get(pred[i], "O")
        if lab.startswith("B-"):
            if cur: spans.append(cur); cur=None
            cur={"start":a,"end":b,"label":lab[2:]}
        elif lab.startswith("I-") and cur and cur["label"]==lab[2:]:
            cur["end"]=b
        else:
            if cur: spans.append(cur); cur=None
    if cur: spans.append(cur)
    snapped=[]
    for s in spans:
        best=None; best_overlap=0
        for rx in PATS.get(s["label"], []):
            for m in rx.finditer(text):
                a,b=m.start(),m.end()
                ov=max(0, min(s["end"],b)-max(s["start"],a))
                if ov>best_overlap:
                    best_overlap=ov; best=(a,b)
        if best_overlap>0:
            s["start"], s["end"] = best
        snapped.append(s)
    uniq=set(); out=[]
    for s in sorted(snapped, key=lambda x:(x["start"],x["end"],x["label"])):
        t=(s["start"],s["end"],s["label"])
        if t in uniq: continue
        uniq.add(t); out.append(s)
    return out
with open(inp,encoding="utf-8") as fi, open(outp,"w",encoding="utf-8") as fo:
    for ln in fi:
        o=json.loads(ln); t=o["text"]
        fo.write(json.dumps({"text":t,"spans":decode(t)},ensure_ascii=False)+"\n")
print("[SNAP] %s -> %s" % (inp, outp))

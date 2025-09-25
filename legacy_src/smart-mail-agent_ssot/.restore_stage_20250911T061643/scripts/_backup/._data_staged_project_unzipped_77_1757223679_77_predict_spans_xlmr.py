#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
def bio_to_spans(text, labels, offsets):
    spans=[]; i=0
    while i<len(labels):
        tag=labels[i]
        if tag.startswith("B-"):
            lab=tag[2:]; start=offsets[i][0]; j=i+1
            while j<len(labels) and labels[j]==f"I-{lab}": j+=1
            end=offsets[j-1][1]
            if end>start: spans.append({"start":int(start),"end":int(end),"label":lab})
            i=j
        else:
            i+=1
    # 合法化（避免 special token 的 0,0）
    return [s for s in spans if s["end"]>s["start"]]
def main():
    in_path=sys.argv[1]; model_dir=sys.argv[2]; out_path=sys.argv[3]
    tok=AutoTokenizer.from_pretrained(model_dir, use_fast=True)
    model=AutoModelForTokenClassification.from_pretrained(model_dir)
    id2label=model.config.id2label
    with open(in_path,"r",encoding="utf-8") as fi, open(out_path,"w",encoding="utf-8") as fo:
        for ln in fi:
            o=json.loads(ln); t=o.get("text","")
            enc=tok(t, return_offsets_mapping=True, truncation=True, max_length=384, return_tensors="pt")
            with torch.no_grad():
                logits=model(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"]).logits[0]
            pred=logits.argmax(-1).tolist()
            labels=[id2label[str(i)] if isinstance(id2label,dict) else id2label[i] for i in pred]
            offsets=[tuple(map(int,xy)) for xy in enc["offset_mapping"][0].tolist()]
            # 去掉 special tokens：offset (0,0) 的位置標成 O
            labels=[("O" if a==b else lab) for lab,(a,b) in zip(labels,offsets)]
            spans=bio_to_spans(t, labels, offsets)
            fo.write(json.dumps({"text":t,"spans":spans},ensure_ascii=False)+"\n")
    print(f"[OK] pred -> {out_path}")
if __name__=="__main__": main()

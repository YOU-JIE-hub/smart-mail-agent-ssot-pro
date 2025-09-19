#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json
from pathlib import Path
from transformers import AutoTokenizer
from seqeval.metrics import f1_score, classification_report
def load(p):
    with open(p,encoding="utf-8") as f:
        for ln in f: yield json.loads(ln)
def to_bio(text, spans, tok, max_len):
    enc=tok(text, return_offsets_mapping=True, truncation=True, max_length=max_len)
    off=enc["offset_mapping"]; tags=["O"]*len(off)
    for sp in spans:
        s,e,lab=sp["start"],sp["end"],sp["label"]; first=True
        for i,(a,b) in enumerate(off):
            if a==b: continue
            if a>=e or b<=s: continue
            tags[i]=f"{'B' if first else 'I'}-{lab}"; first=False
    return [tags[i] for i,(a,b) in enumerate(off) if a!=b]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pred", required=True); ap.add_argument("--gold", required=True); ap.add_argument("--model_dir", required=True); ap.add_argument("--out", required=True); ap.add_argument("--max_len", type=int, default=512)
    a=ap.parse_args()
    tok=AutoTokenizer.from_pretrained(a.model_dir)
    Yt,Yp=[],[]
    for po,go in zip(load(a.pred), load(a.gold)):
        Yt.append(to_bio(go["text"], go.get("spans",[]), tok, a.max_len))
        Yp.append(to_bio(po["text"], po.get("spans",[]), tok, a.max_len))
    f1=f1_score(Yt,Yp); rpt=classification_report(Yt,Yp, digits=4)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(f"F1={f1:.4f}\n\n{rpt}\n", encoding="utf-8")
    print(f"[EVAL] F1={f1:.4f} -> {a.out}")
if __name__ == "__main__": main()

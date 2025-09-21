#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, sys
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
import numpy as np

def load_model(model_dir: Path):
    tok = AutoTokenizer.from_pretrained(model_dir)
    mdl = AutoModelForTokenClassification.from_pretrained(model_dir)
    mdl.eval()
    id2label = mdl.config.id2label if isinstance(mdl.config.id2label, dict) else {int(k):v for k,v in mdl.config.id2label.items()}
    return tok, mdl, id2label

def read_inputs(path: Path):
    if path.suffix.lower()==".jsonl":
        for ln in path.read_text(encoding="utf-8",errors="ignore").splitlines():
            if not ln.strip(): continue
            o=json.loads(ln)
            t=o.get("text") or ((o.get("subject","")+"\n"+o.get("body","")).strip())
            if not t: t=json.dumps(o,ensure_ascii=False)
            yield o.get("id",""), t
    else:
        # 純文字檔：每行一個樣本
        for i,ln in enumerate(path.read_text(encoding="utf-8",errors="ignore").splitlines(),1):
            if ln.strip(): yield f"line-{i:04d}", ln.strip()

def bio_decode(ids, labels, offsets, text):
    spans=[]
    cur=None
    for i,lab in enumerate(labels):
        if lab=="O" or lab is None:
            if cur: spans.append(cur); cur=None
            continue
        if lab.startswith("B-"):
            if cur: spans.append(cur)
            tag=lab[2:]
            st,ed = offsets[i]
            cur={"label":tag,"start":int(st),"end":int(ed)}
        elif lab.startswith("I-"):
            tag=lab[2:]
            if cur and cur["label"]==tag:
                st,ed = offsets[i]
                cur["end"]=int(ed)
            else:
                # 容錯：孤立 I- 視為 B-
                st,ed = offsets[i]
                cur={"label":tag,"start":int(st),"end":int(ed)}
        else:
            if cur: spans.append(cur); cur=None
    if cur: spans.append(cur)
    # SNAP-like: 去重疊（先到先得），保守輸出
    spans_sorted=sorted(spans, key=lambda x:(x["start"], x["end"]))
    out=[]
    last_end=-1
    for s in spans_sorted:
        if s["start"]>=last_end:
            out.append(s); last_end=s["end"]
        # 若有重疊，保留先入（也可改成取較長）
    return out

def predict(model_dir: Path, src: Path, out_tsv: Path, max_len=512, device=None):
    tok, mdl, id2label = load_model(model_dir)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    mdl.to(device)

    with open(out_tsv,"w",encoding="utf-8") as w:
        w.write("id\tlabel\tstart\tend\tspan_text\n")
        for _id, text in read_inputs(src):
            enc = tok(text, return_offsets_mapping=True, truncation=True, max_length=max_len)
            input_ids = torch.tensor([enc["input_ids"]], device=device)
            attn = torch.tensor([enc["attention_mask"]], device=device)
            with torch.no_grad():
                logits = mdl(input_ids, attention_mask=attn).logits[0].cpu().numpy()
            pred_ids = logits.argmax(-1)
            labels = [id2label.get(int(i),"O") for i in pred_ids]
            # 去掉 special tokens 的 offset (-1,-1)
            offsets = enc["offset_mapping"]
            labels_clean=[]; offsets_clean=[]
            for lab,off in zip(labels, offsets):
                st,ed = off
                if st==ed==0 and lab!="O":  # 部分 tokenizer 會給 0,0 在 specials; 安全處理
                    labels_clean.append("O"); offsets_clean.append((0,0))
                else:
                    labels_clean.append(lab); offsets_clean.append(off)
            spans=bio_decode(enc["input_ids"], labels_clean, offsets_clean, text)
            for s in spans:
                frag = text[s["start"]:s["end"]].replace("\t"," ").replace("\n"," ")
                w.write(f"{_id}\t{s['label']}\t{s['start']}\t{s['end']}\t{frag}\n")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--model_dir", default="kie", help="KIE model folder")
    ap.add_argument("--input", required=True, help="txt(each line) or jsonl(text/subject+body)")
    ap.add_argument("--out", default="pred_kie.tsv")
    a=ap.parse_args()
    predict(Path(a.model_dir), Path(a.input), Path(a.out))
    print("[OK] wrote", a.out)

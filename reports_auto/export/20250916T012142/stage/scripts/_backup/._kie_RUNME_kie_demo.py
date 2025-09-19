#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, sys, os
from pathlib import Path
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForTokenClassification
except Exception as e:
    print("[FATAL] 缺少 transformers/torch：", e, file=sys.stderr)
    sys.exit(86)

def load_model(model_dir: Path):
    # 權重存在性檢查
    if not (model_dir/"pytorch_model.bin").exists() and not (model_dir/"model.safetensors").exists():
        msg = "[FATAL] 權重不存在。請將原始權重複製到解壓後的 kie/ 目錄（檔名需與原始一致）。"
        if (model_dir/"PLACE_WEIGHTS_HERE.txt").exists():
            msg += " 參考 PLACE_WEIGHTS_HERE.txt。"
        print(msg, file=sys.stderr); sys.exit(86)
    tok = AutoTokenizer.from_pretrained(model_dir)
    mdl = AutoModelForTokenClassification.from_pretrained(model_dir)
    mdl.eval()
    id2label = getattr(mdl.config, "id2label", {}) or {}
    # id2label 的 key 可能是字串
    if isinstance(id2label, dict):
        id2label = {int(k): v for k, v in id2label.items()}
    else:
        id2label = {i: f"L{i}" for i in range(getattr(mdl.config, "num_labels", 2))}
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
        for i,ln in enumerate(path.read_text(encoding="utf-8",errors="ignore").splitlines(),1):
            if ln.strip(): yield f"line-{i:04d}", ln.strip()

def bio_decode(labels, offsets):
    spans=[]; cur=None
    for i,lab in enumerate(labels):
        st,ed = offsets[i]
        if st==ed==0:  # special token
            continue
        if lab=="O" or lab is None:
            if cur: spans.append(cur); cur=None
            continue
        if lab.startswith("B-"):
            if cur: spans.append(cur)
            cur={"label":lab[2:], "start":int(st), "end":int(ed)}
        elif lab.startswith("I-"):
            tag=lab[2:]
            if cur and cur["label"]==tag:
                cur["end"]=int(ed)
            else:
                cur={"label":tag, "start":int(st), "end":int(ed)}
    if cur: spans.append(cur)
    # 去重疊，先到先得
    out=[]; last_end=-1
    for s in sorted(spans, key=lambda x:(x["start"], x["end"])):
        if s["start"]>=last_end:
            out.append(s); last_end=s["end"]
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
            offsets = enc["offset_mapping"]
            spans=bio_decode(labels, offsets)
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

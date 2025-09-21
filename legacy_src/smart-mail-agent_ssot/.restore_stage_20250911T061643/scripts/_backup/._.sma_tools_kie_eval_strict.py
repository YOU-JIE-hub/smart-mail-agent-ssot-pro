#!/usr/bin/env python3
import argparse, json, torch
from pathlib import Path
from collections import defaultdict
from transformers import AutoTokenizer, AutoModelForTokenClassification

def read_jsonl(p):
    for ln in open(p,'r',encoding='utf-8',errors='ignore'):
        if ln.strip(): yield json.loads(ln)

def bio_decode(labels, offsets):
    spans=[]; cur=None
    for lab,(st,ed) in zip(labels, offsets):
        if (st,ed)==(0,0) or lab=="O":
            if cur: spans.append(cur); cur=None
            continue
        if lab.startswith("B-"):
            if cur: spans.append(cur)
            cur={"label":lab[2:], "start":int(st), "end":int(ed)}
        elif lab.startswith("I-") and cur and cur["label"]==lab[2:]:
            cur["end"]=int(ed)
        else:
            if cur: spans.append(cur); cur=None
    if cur: spans.append(cur)
    out=[]; last=-1
    for s in sorted(spans, key=lambda x:(x["start"],x["end"])):
        if s["start"]>=last: out.append(s); last=s["end"]
    return out

def strict_prf(gold, pred):
    tp=fp=fn=0
    by_label=defaultdict(lambda: {"tp":0,"fp":0,"fn":0})
    for g, p in zip(gold, pred):
        gset={(s["label"], s["start"], s["end"]) for s in g}
        pset={(s["label"], s["start"], s["end"]) for s in p}
        inter=gset & pset
        tp+=len(inter); fp+=len(pset - inter); fn+=len(gset - inter)
        for lab in set([x[0] for x in gset|pset]):
            gL=set([x for x in gset if x[0]==lab]); pL=set([x for x in pset if x[0]==lab])
            interL=gL & pL
            by_label[lab]["tp"]+=len(interL); by_label[lab]["fp"]+=len(pL-interL); by_label[lab]["fn"]+=len(gL-interL)
    P=tp/(tp+fp) if (tp+fp) else 0.0
    R=tp/(tp+fn) if (tp+fn) else 0.0
    F=2*P*R/(P+R) if (P+R) else 0.0
    per={}
    for lab, d in by_label.items():
      p = d["tp"]/(d["tp"]+d["fp"]) if (d["tp"]+d["fp"]) else 0.0
      r = d["tp"]/(d["tp"]+d["fn"]) if (d["tp"]+d["fn"]) else 0.0
      f = 2*p*r/(p+r) if (p+r) else 0.0
      per[lab]={"P":p,"R":r,"F1":f,"tp":d["tp"],"fp":d["fp"],"fn":d["fn"]}
    return (P,R,F,tp,fp,fn, per)

def predict_spans(model_dir, data_path, max_len=512, fp16=False):
    tok = AutoTokenizer.from_pretrained(model_dir)
    kw={"torch_dtype": torch.float16} if fp16 else {}
    mdl = AutoModelForTokenClassification.from_pretrained(model_dir, **kw).eval()

    # --- robust id2label -> labels ---
    raw = mdl.config.id2label
    labels = []
    if isinstance(raw, dict):
        def _lab(i):
            return raw.get(i, raw.get(str(i)))
        for i in range(mdl.config.num_labels):
            li=_lab(i)
            if li is None:  # 退回順序遍歷
                li = list(raw.values())[i]
            labels.append(li)
    else:
        labels = [raw[i] for i in range(mdl.config.num_labels)]

    gold=[]; pred=[]
    for o in read_jsonl(data_path):
        text=o.get("text") or ((o.get("subject","")+"\n"+o.get("body","")).strip())
        enc = tok(text, return_offsets_mapping=True, truncation=True, max_length=max_len)
        with torch.no_grad():
            out = mdl(torch.tensor([enc["input_ids"]]), attention_mask=torch.tensor([enc["attention_mask"]])).logits[0]
        ids = out.argmax(-1).tolist()
        labs=[labels[i] for i in ids]
        pred.append(bio_decode(labs, enc["offset_mapping"]))
        gold.append(o.get("spans",[]))
    return gold, pred

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--model_dir", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--out_prefix", default="reports_auto/kie_eval")
    ap.add_argument("--fp16", action="store_true")
    a=ap.parse_args()
    gold, pred = predict_spans(a.model_dir, a.test, fp16=a.fp16)
    P,R,F,tp,fp,fn, per = strict_prf(gold, pred)
    out_txt=Path(f"{a.out_prefix}.txt"); out_tsv=Path(f"{a.out_prefix}_per_label.tsv")
    out_txt.write_text(
f"""pairs={len(gold)}
strict_span_P={P:.4f}
strict_span_R={R:.4f}
strict_span_F1={F:.4f}
(tp={tp}, fp={fp}, fn={fn})
""", encoding="utf-8")
    with open(out_tsv,"w",encoding="utf-8") as w:
        w.write("label\tP\tR\tF1\ttp\tfp\tfn\n")
        for lab in sorted(per.keys()):
            d=per[lab]; w.write(f"{lab}\t{d['P']:.4f}\t{d['R']:.4f}\t{d['F1']:.4f}\t{d['tp']}\t{d['fp']}\t{d['fn']}\n")
    print("[OUT]", out_txt, out_tsv)

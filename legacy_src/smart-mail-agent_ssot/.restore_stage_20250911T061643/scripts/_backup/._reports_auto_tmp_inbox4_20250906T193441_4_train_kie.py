#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, random
from pathlib import Path
from typing import List, Dict, Any
import numpy as np, torch
from torch.utils.data import Dataset
from transformers import (AutoTokenizer, AutoModelForTokenClassification,
                          DataCollatorForTokenClassification, Trainer, TrainingArguments)
from seqeval.metrics import f1_score
def load_jsonl(p: Path):
    with p.open("r", encoding="utf-8") as f:
        for ln in f: yield json.loads(ln)
def collect_labels(p: Path) -> List[str]:
    labs=set()
    for o in load_jsonl(p):
        for s in o.get("spans",[]): labs.add(s["label"])
    return ["O"] + [f"{p}-{l}" for l in sorted(labs) for p in ("B","I")]
def to_item(text: str, spans: List[Dict[str,Any]], tok, max_len: int, label_list: List[str]):
    enc = tok(text, truncation=True, max_length=max_len, return_offsets_mapping=True, return_special_tokens_mask=True)
    offs, sp = enc["offset_mapping"], enc["special_tokens_mask"]
    tags = ["O"]*len(offs)
    for spn in spans:
        s,e,lab = spn["start"], spn["end"], spn["label"]; first=True
        for i,(a,b) in enumerate(offs):
            if sp[i] or a==b: continue
            if a>=e or b<=s: continue
            tags[i] = f"{'B' if first else 'I'}-{lab}"; first=False
    idmap={l:i for i,l in enumerate(label_list)}
    lbl=[(-100 if (sp[i] or a==b) else idmap.get(tags[i],0)) for i,(a,b) in enumerate(offs)]
    return {"input_ids":enc["input_ids"],"attention_mask":enc["attention_mask"],"labels":lbl}
class DS(Dataset):
    def __init__(self, texts, spans, tok, max_len, label_list):
        self.items=[to_item(t,s,tok,max_len,label_list) for t,s in zip(texts,spans)]
    def __len__(self): return len(self.items)
    def __getitem__(self,i):
        import torch; return {k: torch.tensor(v) for k,v in self.items[i].items()}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--silver", required=True)
    ap.add_argument("--model_dir", required=True)
    ap.add_argument("--base_model", default="xlm-roberta-base")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max_len", type=int, default=512)
    a=ap.parse_args()
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    tok = AutoTokenizer.from_pretrained(a.base_model, local_files_only=bool(int(os.environ.get('SMA_LOCAL_ONLY','0'))))
    labels = collect_labels(Path(a.silver))
    id2={i:l for i,l in enumerate(labels)}
    texts, spans = [], []
    for o in load_jsonl(Path(a.silver)): texts.append(o["text"]); spans.append(o.get("spans",[]))
    ds = DS(texts, spans, tok, a.max_len, labels)
    model = AutoModelForTokenClassification.from_pretrained(a.base_model, num_labels=len(labels, local_files_only=bool(int(os.environ.get('SMA_LOCAL_ONLY','0')))), id2label=id2, label2id={l:i for i,l in id2.items()})
    collator = DataCollatorForTokenClassification(tok)
    def metrics(ev):
        import numpy as np
        lg, lb = ev
        pd = np.argmax(lg, axis=-1)
        tru, pre = [], []
        for pr, lr in zip(pd, lb):
            t,p=[],[]
            for pi,li in zip(pr,lr):
                if li==-100: continue
                t.append(id2[li]); p.append(id2[pi])
            tru.append(t); pre.append(p)
        from seqeval.metrics import f1_score
        return {"f1": f1_score(tru, pre)}
    args = TrainingArguments(output_dir=a.model_dir, num_train_epochs=a.epochs, learning_rate=a.lr, per_device_train_batch_size=a.batch, seed=a.seed, save_strategy="epoch", evaluation_strategy="no")
    tr = Trainer(model=model, args=args, train_dataset=ds, tokenizer=tok, data_collator=collator, compute_metrics=metrics)
    tr.train()
    Path(a.model_dir).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(a.model_dir); tok.save_pretrained(a.model_dir)
    Path(a.model_dir,"labels.json").write_text(json.dumps({"labels":labels},ensure_ascii=False), encoding="utf-8")
    print(f"[MODEL] saved -> {a.model_dir}")
if __name__ == "__main__": main()

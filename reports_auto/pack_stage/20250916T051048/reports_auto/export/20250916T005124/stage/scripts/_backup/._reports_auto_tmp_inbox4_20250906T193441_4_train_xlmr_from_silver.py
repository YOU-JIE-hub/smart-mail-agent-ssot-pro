#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os, random, math
from pathlib import Path
import numpy as np, torch
from transformers import (AutoTokenizer, AutoModelForTokenClassification,
                          DataCollatorForTokenClassification, Trainer, TrainingArguments)
from seqeval.metrics import f1_score, precision_score, recall_score, classification_report

def set_seed(s):
    random.seed(s); np.random.seed(s); torch.manual_seed(s)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(s)

def build_bio_labels(rule_labels):
    bio=["O"]
    for lab in rule_labels:
        bio += [f"B-{lab}", f"I-{lab}"]
    id2label = {i:l for i,l in enumerate(bio)}
    label2id = {l:i for i,l in id2label.items()}
    return bio, id2label, label2id

def load_rule_labels(rules_path):
    import yaml
    obj = yaml.safe_load(Path(rules_path).read_text(encoding="utf-8"))
    return list(obj.get("labels", []))

def read_silver(path):
    rows=[]
    with open(path, encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln)
            rows.append({"text":o["text"], "spans":o.get("spans",[])})
    return rows

def bio_encode_row(text, spans, tokenizer, label2id, max_length):
    # 1) 以字元建立標註圖
    char_tag = ["O"]*len(text)
    for sp in spans:
        s,e,lab = sp["start"], sp["end"], sp["label"]
        if s<e and 0<=s<len(text):
            char_tag[s] = f"B-{lab}"
            for i in range(s+1, min(e, len(text))):
                char_tag[i] = f"I-{lab}"
    # 2) tokenize 並對齊
    enc = tokenizer(text, return_offsets_mapping=True, truncation=True, max_length=max_length)
    offsets = enc["offset_mapping"]; labels=[]
    prev_tag="O"
    for (st,ed) in offsets:
        if st==ed:  # special tokens
            labels.append("O"); continue
        # 這顆 token 以「第一個被標註的字元」決定標籤
        tok_tag = "O"
        for i in range(st, ed):
            if i < len(char_tag) and char_tag[i] != "O":
                tok_tag = char_tag[i]; break
        # 避免 I-* 起頭：若是 I-*，而前一顆不是同類 B/I，轉成 B-*
        if tok_tag.startswith("I-"):
            base = tok_tag[2:]
            if not (prev_tag.endswith(base) and prev_tag!="O"):
                tok_tag = f"B-{base}"
        labels.append(tok_tag)
        prev_tag = tok_tag
    enc.pop("offset_mapping", None)
    enc["labels"] = [label2id.get(x,"O") if isinstance(x,str) else 0 for x in labels]
    enc["labels"] = [label2id.get(x,0) for x in labels]
    return enc

class JsonlDataset(torch.utils.data.Dataset):
    def __init__(self, rows, tokenizer, label2id, max_length):
        self.items=[]
        for r in rows:
            self.items.append(bio_encode_row(r["text"], r["spans"], tokenizer, label2id, max_length))
    def __len__(self): return len(self.items)
    def __getitem__(self, i): return {k:torch.tensor(v) for k,v in self.items[i].items()}

def make_compute_metrics(id2label):
    def decode(pred):
        # pred.predictions: [bsz, seq_len, num_labels]
        p = np.argmax(pred.predictions, axis=-1)
        y = pred.label_ids
        def to_tags(arr):
            return [[id2label.get(int(t), "O") for t in seq] for seq in arr]
        return to_tags(p), to_tags(y)
    def compute(pred):
        P, Y = decode(pred)
        # 去掉 padding：將與 label 長度對齊的 O 位置保留 seqeval 會處理
        return {
            "precision": precision_score(Y,P),
            "recall":    recall_score(Y,P),
            "f1":        f1_score(Y,P)
        }
    return compute

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--silver_train", required=True)
    ap.add_argument("--silver_val",   required=True)
    ap.add_argument("--outdir",       required=True)
    ap.add_argument("--rules", default=".sma_tools/ruleset.yml")
    ap.add_argument("--model_name", default="xlm-roberta-base")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max_length", type=int, default=384)
    args=ap.parse_args()

    set_seed(args.seed)
    labels = load_rule_labels(args.rules)
    bio, id2label, label2id = build_bio_labels(labels)
    tok = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
    train_rows = read_silver(args.silver_train)
    val_rows   = read_silver(args.silver_val)
    ds_train = JsonlDataset(train_rows, tok, label2id, args.max_length)
    ds_val   = JsonlDataset(val_rows, tok, label2id, args.max_length)

    model = AutoModelForTokenClassification.from_pretrained(
        args.model_name, num_labels=len(bio), id2label=id2label, label2id=label2id
    )

    args_tr = TrainingArguments(
        output_dir=args.outdir,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        gradient_accumulation_steps=2,
        learning_rate=3e-5,
        num_train_epochs=args.epochs,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        logging_steps=50,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        report_to=[]
    )
    trainer = Trainer(
        model=model,
        args=args_tr,
        train_dataset=ds_train,
        eval_dataset=ds_val,
        tokenizer=tok,
        data_collator=DataCollatorForTokenClassification(tok),
        compute_metrics=make_compute_metrics(id2label)
    )
    trainer.train()
    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    trainer.save_model(args.outdir)
    tok.save_pretrained(args.outdir)
    print("[TRAIN] saved ->", args.outdir)

if __name__ == "__main__":
    main()

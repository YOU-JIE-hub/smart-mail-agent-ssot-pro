import json, argparse, random
from pathlib import Path
from typing import List, Dict
import numpy as np
from transformers import AutoTokenizer, AutoModelForTokenClassification, DataCollatorForTokenClassification, Trainer, TrainingArguments
from seqeval.metrics import precision_score, recall_score, f1_score

LABEL_ALL_SUBTOKENS = True

def read_jsonl(p): return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines()]

def build_label_list(*files):
    labs=set()
    for p in files:
        if not Path(p).exists(): continue
        for r in read_jsonl(p):
            for s in r.get("labels",[]): labs.add(s["label"])
    base=sorted(labs); tags=["O"]+[t for b in base for t in (f"B-{b}", f"I-{b}")]
    return tags

def align_bio(text:str, spans:List[Dict], enc, label2id):
    offsets = enc.encodings[0].offsets
    tags=["O"]*len(offsets)
    for sp in spans:
        s,e,lab = sp["start"], sp["end"], sp["label"]
        begun=False
        for i,(a,b) in enumerate(offsets):
            if a==b: continue
            if a>=e or b<=s: continue
            tags[i] = ("B-" if not begun else "I-")+lab; begun=True
    ids=[label2id.get(t,0) for t in tags]
    # pad 對齊 input_ids 長度
    need = len(enc["input_ids"][0]) - len(ids)
    if need>0: ids += [label2id["O"]]*need
    return ids

def make_dataset(items, tok, label2id):
    ds=[]
    for r in items:
        enc = tok(r["text"], truncation=True, max_length=512, return_offsets_mapping=True)
        labels = align_bio(r["text"], r.get("labels",[]), enc, label2id)
        ds.append({**{k:v for k,v in enc.items() if k!="offset_mapping"}, "labels": labels})
    return ds

def compute_metrics(p, id2label):
    preds, labels = p
    preds = np.argmax(preds, axis=-1)
    true_tags, pred_tags = [], []
    for p_i, l_i in zip(preds, labels):
        tt, pt = [], []
        for pi, li in zip(p_i, l_i):
            if li==-100: continue
            tt.append(id2label[li]); pt.append(id2label[pi])
        true_tags.append(tt); pred_tags.append(pt)
    return {"precision": precision_score(true_tags, pred_tags), "recall": recall_score(true_tags, pred_tags), "f1": f1_score(true_tags, pred_tags)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--train", default="data/kie/train.jsonl")
    ap.add_argument("--val", default="data/kie/val.jsonl")
    ap.add_argument("--test", default="data/kie/test.jsonl")
    ap.add_argument("--model", default="xlm-roberta-base")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out_dir", default="artifacts/kie_xlmr")
    args=ap.parse_args()

    random.seed(args.seed); np.random.seed(args.seed)
    labels = build_label_list(args.train, args.val, args.test)
    label2id = {t:i for i,t in enumerate(labels)}; id2label={i:t for t,i in label2id.items()}

    tok = AutoTokenizer.from_pretrained(args.model)
    mdl = AutoModelForTokenClassification.from_pretrained(args.model, num_labels=len(labels), id2label=id2label, label2id=label2id)

    trn = read_jsonl(args.train)
    val = read_jsonl(args.val) if Path(args.val).exists() else []

    trn_ds = make_dataset(trn, tok, label2id)
    val_ds = make_dataset(val, tok, label2id) if val else None

    args_out = TrainingArguments(output_dir=args.out_dir, learning_rate=args.lr, per_device_train_batch_size=args.bs, per_device_eval_batch_size=args.bs, num_train_epochs=args.epochs, weight_decay=0.01, evaluation_strategy=("epoch" if val else "no"), save_strategy=("epoch" if val else "no"), logging_steps=50, seed=args.seed, fp16=False)

    trainer = Trainer(model=mdl, args=args_out, train_dataset=trn_ds, eval_dataset=val_ds, data_collator=DataCollatorForTokenClassification(tok), tokenizer=tok, compute_metrics=lambda p: compute_metrics(p, id2label))
    trainer.train(); trainer.save_model(args.out_dir); tok.save_pretrained(args.out_dir)
    print(f"[SAVED] {args.out_dir}")

if __name__=="__main__":
    main()

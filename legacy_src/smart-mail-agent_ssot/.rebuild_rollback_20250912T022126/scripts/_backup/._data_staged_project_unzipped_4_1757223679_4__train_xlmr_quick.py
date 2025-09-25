import argparse, json, random, numpy as np, torch
from pathlib import Path
from transformers import (AutoTokenizer, AutoModelForTokenClassification,
                          DataCollatorForTokenClassification, Trainer, TrainingArguments)

ap=argparse.ArgumentParser()
ap.add_argument("--train", required=True)
ap.add_argument("--val",   required=True)
ap.add_argument("--out",   required=True)
ap.add_argument("--max_steps", type=int, default=400)   # default 加大
ap.add_argument("--epochs", type=float, default=1.0)
ap.add_argument("--subset", type=int, default=0)
ap.add_argument("--max_length", type=int, default=384)
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--log", default=".sma_logs/kie_train.log")
args=ap.parse_args()

random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
tok = AutoTokenizer.from_pretrained("xlm-roberta-base", use_fast=True)

def load_rows(p, limit=0):
    rows=[json.loads(x) for x in open(p,encoding="utf-8")]
    return rows[:limit] if limit>0 else rows

def to_bio(rows):
    out=[]
    for o in rows:
        t=o["text"]; spans=o.get("spans",[])
        enc=tok(t, return_offsets_mapping=True, truncation=True, max_length=args.max_length)
        offs=enc["offset_mapping"]          # list of (a,b)
        tags=["O"]*len(offs)
        # 改成「只要與實體 span 有重疊就標 B/I」
        for s in spans:
            sA, sB = s["start"], s["end"]
            started=False
            for i,(a,b) in enumerate(offs):
                if a==b: continue
                overlap = max(0, min(b, sB) - max(a, sA))
                if overlap>0:
                    tags[i]=("B-" if not started else "I-")+s["label"]
                    started=True
        enc.pop("offset_mapping",None)
        out.append((enc,tags))
    return out

tr = to_bio(load_rows(args.train, args.subset))
va = to_bio(load_rows(args.val,   min(args.subset, len(open(args.val,encoding="utf-8").readlines())) if args.subset else 0))

# 標籤集合
tags=set(["O"]+[f"{p}-{l}" for l in ["amount","date_time","env","sla"] for p in ["B","I"]])
for _,ts in tr+va: tags.update(ts)
id2label={i:l for i,l in enumerate(sorted(tags))}
label2id={l:i for i,l in id2label.items()}

class DS(torch.utils.data.Dataset):
    def __init__(self,bio): self.bio=bio
    def __len__(self): return len(self.bio)
    def __getitem__(self,i):
        enc,tg=self.bio[i]
        enc["labels"]=[label2id.get(t,0) for t in tg]
        return {k:torch.tensor(v) for k,v in enc.items()}

model = AutoModelForTokenClassification.from_pretrained(
    "xlm-roberta-base",
    num_labels=len(id2label), id2label=id2label, label2id=label2id
)

args_tr = TrainingArguments(
    output_dir=args.out,
    max_steps=args.max_steps,                # 控制整體時間
    learning_rate=3e-5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    eval_strategy="steps",
    eval_steps=50,
    logging_steps=25,                        # 規律輸出
    report_to="none",
    save_strategy="no",                      # smoke: 只在結尾 save
    disable_tqdm=True,
    seed=args.seed,
    gradient_accumulation_steps=2,           # 提升有效 batch
    warmup_ratio=0.1
)

trainer = Trainer(
    model=model, args=args_tr, tokenizer=tok,
    data_collator=DataCollatorForTokenClassification(tokenizer=tok),
    train_dataset=DS(tr), eval_dataset=DS(va)
)
print(f"[TRAIN] rows: train={len(tr)} val={len(va)} max_steps={args.max_steps}", flush=True)
trainer.train()
trainer.save_model(args.out); tok.save_pretrained(args.out)
print("[OK] saved ->", args.out, flush=True)
Path(args.log).write_text("[OK] quick train finished\n", encoding="utf-8")

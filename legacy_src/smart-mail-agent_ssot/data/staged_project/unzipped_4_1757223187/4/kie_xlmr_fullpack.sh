#!/usr/bin/env bash
set -Eeuo pipefail; set -o errtrace; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"; cd "$ROOT" || exit 96
TS="$(date +%Y-%m-%d_%H%M%S)"; LOG=".sma_logs/kie_xlmr_fullpack_${TS}.log"; exec > >(tee -a "$LOG") 2>&1
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY="$(command -v python3 || command -v python)"; fi
GOLD="${1:-data/kie/test_real.jsonl}"
IN_T="${IN_T:-data/intent/train_aug.jsonl}"; IN_V="${IN_V:-data/intent/val_aug.jsonl}"
[ -s "$IN_T" ] || { echo "[FATAL] train_aug missing: $IN_T"; exit 91; }
[ -s "$IN_V" ] || { echo "[FATAL] val_aug missing:   $IN_V"; exit 92; }
[ -s "$GOLD" ] || { echo "[FATAL] GOLD missing:      $GOLD"; exit 93; }
echo "[INFO] PY=$PY"; echo "[INFO] GOLD=$GOLD"
mkdir -p data/kie reports_auto artifacts/kie_xlmr

# A) 規則生成 silver
$PY - <<'PY'
import json,re,yaml
def spans(t,pats,lab):
    S=[]
    for p in pats: S += [{"start":m.start(),"end":m.end(),"label":lab} for m in p.finditer(t)]
    return S
import pathlib
rules=yaml.safe_load(open(".sma_tools/ruleset.yml","r",encoding="utf-8"))
import re
PAM=[re.compile(r, re.I) for r in rules["patterns"]["amount"]]
PDT=[re.compile(r, re.I) for r in rules["patterns"]["date_time"]]
PEN=[re.compile(r, re.I) for r in rules["patterns"]["env"]]
PSL=[re.compile(r, re.I) for r in rules["patterns"].get("sla",[])]
def run(inp,outp):
    n=0
    with open(inp,"r",encoding="utf-8") as fi, open(outp,"w",encoding="utf-8") as fo:
        for ln in fi:
            o=json.loads(ln); t=o.get("text","")
            s=spans(t,PAM,"amount")+spans(t,PDT,"date_time")+spans(t,PEN,"env")+spans(t,PSL,"sla")
            fo.write(json.dumps({"text":t,"spans":s},ensure_ascii=False)+"\n"); n+=1
    print(f"[SILVER] {inp} -> {outp} lines={n}")
run("data/intent/train_aug.jsonl","data/kie/silver_train.jsonl")
run("data/intent/val_aug.jsonl","data/kie/silver_val.jsonl")
PY

# B) 訓練
$PY - <<'PY'
import json, os, random, numpy as np, torch
from transformers import (AutoTokenizer, AutoModelForTokenClassification,
                          DataCollatorForTokenClassification, Trainer, TrainingArguments)
random.seed(42); np.random.seed(42); torch.manual_seed(42)
tok=AutoTokenizer.from_pretrained("xlm-roberta-base", use_fast=True)

def load_rows(p): return [json.loads(l) for l in open(p,encoding="utf-8")]
def to_bio_row(t, spans):
    enc=tok(t, return_offsets_mapping=True, truncation=True, max_length=384)
    offs=enc["offset_mapping"]; L=["O"]*len(offs)
    for s in sorted(spans, key=lambda x:x["start"]):
        covered=[]
        for i,(a,b) in enumerate(offs):
            if a==b: continue
            if not (b<=s["start"] or a>=s["end"]): covered.append(i)  # overlap>0
        if covered:
            L[covered[0]]="B-"+s["label"]
            for j in covered[1:]: L[j]="I-"+s["label"]
    # 掃掉 special offsets
    L=[("O" if a==b else lab) for lab,(a,b) in zip(L,offs)]
    enc.pop("offset_mapping",None)
    return enc, L

def to_ds(rows):
    es=[]; ls=[]
    for o in rows:
        enc,tags = to_bio_row(o["text"], o.get("spans",[]))
        es.append(enc); ls.append(tags)
    return es, ls

train=load_rows("data/kie/silver_train.jsonl")
val  =load_rows("data/kie/silver_val.jsonl")
Etr,Ltr = to_ds(train); Eval,Lval = to_ds(val)
tags=set()
for L in Ltr+Lval: tags.update(L)
for base in ["O","B-amount","I-amount","B-date_time","I-date_time","B-env","I-env","B-sla","I-sla"]:
    tags.add(base)
id2label={i:l for i,l in enumerate(sorted(tags))}
label2id={l:i for i,l in id2label.items()}

import torch.utils.data as tud
class DS(tud.Dataset):
    def __init__(self, E, L): self.E=E; self.L=L
    def __len__(self): return len(self.E)
    def __getitem__(self, idx):
        enc=dict(self.E[idx]); enc["labels"]=[label2id.get(t, label2id["O"]) for t in self.L[idx]]
        return {k:torch.tensor(v) for k,v in enc.items()}
tr_ds=DS(Etr,Ltr); va_ds=DS(Eval,Lval)

model=AutoModelForTokenClassification.from_pretrained("xlm-roberta-base",
        num_labels=len(id2label), id2label=id2label, label2id=label2id)
args=TrainingArguments(output_dir="artifacts/kie_xlmr",
        per_device_train_batch_size=8, per_device_eval_batch_size=8,
        num_train_epochs=3, learning_rate=3e-5, evaluation_strategy="epoch",
        save_strategy="epoch", load_best_model_at_end=True,
        metric_for_best_model="eval_loss", greater_is_better=False, seed=42)
trainer=Trainer(model=model, args=args, tokenizer=tok,
    data_collator=DataCollatorForTokenClassification(tokenizer=tok),
    train_dataset=tr_ds, eval_dataset=va_ds)
trainer.train()
trainer.save_model("artifacts/kie_xlmr"); tok.save_pretrained("artifacts/kie_xlmr")
print("[TRAIN] saved -> artifacts/kie_xlmr")
PY

# C) 推論 + 評測（test_real）
$PY sma_tools/predict_spans_xlmr.py data/kie/test_real.jsonl artifacts/kie_xlmr reports_auto/kie_pred_xlmr.jsonl
$PY sma_tools/kie_eval_full.py reports_auto/kie_pred_xlmr.jsonl data/kie/test_real.jsonl reports_auto/kie_eval_xlmr.txt
echo "[OK] -> reports_auto/kie_eval_xlmr.txt"

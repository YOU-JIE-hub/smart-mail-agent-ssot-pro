#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, os, re, random, numpy as np, torch, yaml
from pathlib import Path
from transformers import (AutoTokenizer, AutoModelForTokenClassification,
                          DataCollatorForTokenClassification, Trainer, TrainingArguments,
                          EarlyStoppingCallback)
from seqeval.metrics import f1_score, precision_score, recall_score

def set_seed(seed: int):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)

def load_rules(p: Path):
    obj = yaml.safe_load(p.read_text(encoding="utf-8"))
    base_labels = obj.get("labels", [])
    pats = {k: [re.compile(rx, re.I) for rx in v] for k, v in obj.get("patterns", {}).items()}
    return base_labels, pats

def spans_by_rules(text: str, pats):
    spans=[]
    for lab, regs in pats.items():
        for rgx in regs:
            for m in rgx.finditer(text):
                spans.append((m.start(), m.end(), lab))
    return sorted(spans, key=lambda x:(x[0],x[1]))

def ensure_silver(in_jsonl: Path, out_jsonl: Path, pats):
    if out_jsonl.exists() and out_jsonl.stat().st_size>0: return
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with in_jsonl.open("r",encoding="utf-8") as fi, out_jsonl.open("w",encoding="utf-8") as fo:
        for ln in fi:
            o=json.loads(ln); t=o.get("text") or o.get("body") or ""
            s=[{"start":a,"end":b,"label":lab} for a,b,lab in spans_by_rules(t,pats)]
            fo.write(json.dumps({"text":t,"spans":s},ensure_ascii=False)+"\n")

def build_label_list(base_labels):
    labs=["O"]
    for lab in base_labels: labs += [f"B-{lab}", f"I-{lab}"]
    return labs

def assign_bio(text, spans, tokenizer, max_len):
    enc = tokenizer(text, return_offsets_mapping=True, truncation=True, max_length=max_len)
    offs = enc["offset_mapping"]; tags=["O"]*len(offs)
    spans = sorted([(s["start"],s["end"],s["label"]) for s in spans], key=lambda x:(x[0],x[1]))
    for s,e,lab in spans:
        started=False
        for i,(ts,te) in enumerate(offs):
            if ts==te==0: continue
            if not (te<=s or ts>=e):
                tags[i] = f"I-{lab}" if started else f"B-{lab}"; started=True
    label_ids=[-100 if ts==te==0 else 0 for ts,te in offs]
    enc.pop("offset_mapping", None)
    return enc, tags, label_ids, offs

class JsonlTokenDataset(torch.utils.data.Dataset):
    def __init__(self, jsonl_path: Path, tokenizer, label2id, max_len=256):
        self.rows=[]
        with jsonl_path.open("r",encoding="utf-8") as f:
            for ln in f:
                o=json.loads(ln); t=o["text"]; spans=o.get("spans",[])
                enc,tags,_,_ = assign_bio(t, spans, tokenizer, max_len)
                enc["labels"] = [label2id.get(tag,0) if tag!="O" else label2id["O"]
                                 if tag!=-100 else -100 for tag in
                                 (tags if tags else ["O"]*sum(1 for _ in enc["input_ids"]))]
                self.rows.append(enc)
    def __len__(self): return len(self.rows)
    def __getitem__(self,idx): return self.rows[idx]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--train_jsonl", required=True)
    ap.add_argument("--val_jsonl",   required=True)
    ap.add_argument("--test_jsonl",  required=True)  # 用來推論與最終評測（text 欄）
    ap.add_argument("--rules", default=".sma_tools/ruleset.yml")
    ap.add_argument("--model_name", default="xlm-roberta-base")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--seed",   type=int, default=42)
    ap.add_argument("--out_dir", default="artifacts/kie_xlmr")
    ap.add_argument("--max_length", type=int, default=256)
    args=ap.parse_args()

    set_seed(args.seed)
    base_labels, pats = load_rules(Path(args.rules))
    label_list = ["O"] + [f"{p}-{l}" for l in base_labels for p in ("B","I")]
    label2id={lab:i for i,lab in enumerate(label_list)}
    id2label={i:lab for lab,i in label2id.items()}

    out_dir=Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir/"labels.json").write_text(json.dumps({"labels":label_list},ensure_ascii=False), encoding="utf-8")

    # 產銀標（規則）供訓練
    silver_train = Path("data/kie/silver_train.jsonl")
    silver_val   = Path("data/kie/silver_val.jsonl")
    ensure_silver(Path(args.train_jsonl), silver_train, pats)
    ensure_silver(Path(args.val_jsonl),   silver_val, pats)

    tok=AutoTokenizer.from_pretrained(args.model_name)
    collator = DataCollatorForTokenClassification(tokenizer=tok)
    ds_tr = JsonlTokenDataset(silver_train, tok, label2id, max_len=args.max_length)
    ds_va = JsonlTokenDataset(silver_val,   tok, label2id, max_len=args.max_length)

    model=AutoModelForTokenClassification.from_pretrained(
        args.model_name, num_labels=len(label_list), id2label=id2label, label2id=label2id
    )

    def compute_metrics(p):
        preds=np.argmax(p.predictions, axis=2)
        y_true=[]; y_pred=[]
        for pr, lb in zip(preds, p.label_ids):
            t_seq=[]; p_seq=[]
            for p_i, l_i in zip(pr, lb):
                if l_i==-100: continue
                t_seq.append(id2label[int(l_i)])
                p_seq.append(id2label[int(p_i)])
            y_true.append(t_seq); y_pred.append(p_seq)
        return {"precision":precision_score(y_true,y_pred),
                "recall":recall_score(y_true,y_pred),
                "f1":f1_score(y_true,y_pred)}

    args_tr=TrainingArguments(
        output_dir=str(out_dir/"hf_runs"),
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        learning_rate=5e-5,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=50,
        save_total_limit=2,
        seed=args.seed,
        fp16=torch.cuda.is_available(),
        report_to=[],
    )
    trainer=Trainer(model=model, args=args_tr, train_dataset=ds_tr, eval_dataset=ds_va,
                    tokenizer=tok, data_collator=collator, compute_metrics=compute_metrics,
                    callbacks=[EarlyStoppingCallback(early_stopping_patience=2)])
    trainer.train()
    trainer.save_model(str(out_dir))

    # 用 test_jsonl 推論 -> reports_auto/kie_pred_from_test.jsonl + kie_pred.jsonl
    pred_out = Path("reports_auto")/f"kie_pred_from_{Path(args.test_jsonl).stem}.jsonl"
    generic  = Path("reports_auto")/"kie_pred.jsonl"
    pred_out.parent.mkdir(parents=True, exist_ok=True)

    with open(args.test_jsonl, "r", encoding="utf-8") as fi, open(pred_out,"w",encoding="utf-8") as fo:
        for ln in fi:
            o=json.loads(ln); t=o["text"]
            enc=tok(t, return_offsets_mapping=True, truncation=True, max_length=args.max_length, return_tensors="pt")
            offs=enc.pop("offset_mapping")[0].tolist()
            enc={k:v.to(model.device) for k,v in enc.items()}
            with torch.no_grad(): logits=model(**enc).logits[0].cpu().numpy()
            pred_ids=np.argmax(logits, axis=1)
            # span 解碼
            spans=[]; cur=None
            for lab_id,(ts,te) in zip(pred_ids, offs):
                if ts==te==0: continue
                lab=id2label[int(lab_id)]
                if lab.startswith("B-"):
                    if cur: spans.append(cur)
                    cur={"start":ts,"end":te,"label":lab[2:]}
                elif lab.startswith("I-") and cur and cur["label"]==lab[2:]:
                    cur["end"]=te
                else:
                    if cur: spans.append(cur); cur=None
            if cur: spans.append(cur)
            fo.write(json.dumps({"text":t,"spans":spans},ensure_ascii=False)+"\n")
    # 同步泛名
    generic.write_text(pred_out.read_text(encoding="utf-8"), encoding="utf-8")

    # 輸出 val 指標
    eval_res=trainer.evaluate()
    (Path("reports_auto")/"kie_val_metrics.json").write_text(
        json.dumps(eval_res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[OK] saved model to", out_dir)
    print("[OK] pred ->", pred_out, "and", generic)

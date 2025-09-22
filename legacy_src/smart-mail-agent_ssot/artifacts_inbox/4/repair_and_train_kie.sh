#!/usr/bin/env bash
# repair_and_train_kie.sh — 修復 regex_stub → 用規則產銀標並訓練 XLM-R，最後在 GOLD 上評測
set -Eeuo pipefail; set -o errtrace; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"; cd "$ROOT" || exit 96
[ -f ".venv/bin/activate" ] && source .venv/bin/activate 2>/dev/null || true
mkdir -p .sma_logs reports_auto artifacts/kie_xlmr data/kie

# ---- 參數 ----
TRAIN="${1:-data/intent/train_aug.jsonl}"
VAL="${2:-data/intent/val_aug.jsonl}"
GOLD="${3:-data/kie/test_real.jsonl}"
OUTDIR="${4:-artifacts/kie_xlmr}"
EPOCHS="${EPOCHS:-3}"; SEED="${SEED:-42}"
TS="$(date +%Y-%m-%d_%H%M%S)"
LOG=".sma_logs/kie_repair_${TS}.log"; exec > >(tee -a "$LOG") 2>&1

echo "[INFO] TRAIN=$TRAIN"; echo "[INFO] VAL=$VAL"; echo "[INFO] GOLD=$GOLD"; echo "[INFO] OUTDIR=$OUTDIR"
[ -s "$TRAIN" ] || { echo "[FATAL] train not found: $TRAIN"; exit 91; }
[ -s "$VAL" ]   || { echo "[FATAL] val not found: $VAL"; exit 92; }
[ -s "$GOLD" ]  || { echo "[FATAL] gold not found: $GOLD"; exit 93; }

# ---- 檢查並備份 regex_stub 佔位 ----
if [ -f "$OUTDIR/config.json" ] && jq -e '.model_type=="regex_stub"' "$OUTDIR/config.json" >/dev/null 2>&1; then
  BAK="${OUTDIR}.stub.$TS"; echo "[WARN] regex_stub detected → backup to $BAK"
  mkdir -p "$BAK"; cp -a "$OUTDIR"/. "$BAK"/; rm -rf "$OUTDIR"/* || true
fi

# ---- 產銀標（依 .sma_tools/ruleset.yml）----
SILV_T="data/kie/silver_train.jsonl"; SILV_V="data/kie/silver_val.jsonl"
python - <<'PY'
import json, re, yaml, sys, os
from pathlib import Path
rules = Path(".sma_tools/ruleset.yml")
if not rules.exists(): sys.exit("[FATAL] missing .sma_tools/ruleset.yml")
cfg = yaml.safe_load(rules.read_text(encoding="utf-8"))
pats = {k:[re.compile(rx, re.I) for rx in v] for k,v in cfg.get("patterns",{}).items()}
def spans(t):
    out=[]; 
    for lab,rxs in pats.items():
        for r in rxs:
            for m in r.finditer(t):
                out.append({"start":m.start(),"end":m.end(),"label":lab})
    # 去重 / 合併重疊（簡單去重）
    uniq={(s["start"],s["end"],s["label"]) for s in out}
    return [{"start":a,"end":b,"label":c} for (a,b,c) in sorted(uniq)]
def run(inp, outp):
    n=0
    with open(inp,encoding="utf-8") as fi, open(outp,"w",encoding="utf-8") as fo:
        for ln in fi:
            o=json.loads(ln); t=o.get("text","")
            fo.write(json.dumps({"text":t,"spans":spans(t)},ensure_ascii=False)+"\n"); n+=1
    print(f"[SILVER] {inp} -> {outp} lines={n}")
run(os.environ["TRAIN"], os.environ["SILV_T"])
run(os.environ["VAL"],   os.environ["SILV_V"])
PY
# env for python above
) 2>/dev/null || true; export TRAIN="$TRAIN" SILV_T="$SILV_T" SILV_V="$SILV_V"

# ---- 訓練 XLM-R（BIO）----
python - <<'PY'
import json, os, random, numpy as np, torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForTokenClassification, DataCollatorForTokenClassification, Trainer, TrainingArguments
from seqeval.metrics import f1_score, precision_score, recall_score

SEED=int(os.getenv("SEED","42")); random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
if torch.cuda.is_available(): torch.cuda.manual_seed_all(SEED)

MODEL_NAME="xlm-roberta-base"
TRAIN=os.environ["SILV_T"]; VAL=os.environ["SILV_V"]; OUTDIR=os.environ["OUTDIR"]
Path(OUTDIR).mkdir(parents=True, exist_ok=True)
tok=AutoTokenizer.from_pretrained(MODEL_NAME)

# labels
def collect_labels(paths):
    labs=set(); 
    for p in paths:
        for ln in open(p,encoding="utf-8"):
            for s in json.loads(ln).get("spans",[]): labs.add(s["label"])
    labs=sorted(labs)
    id2label={0:"O"}; label2id={"O":0}; i=1
    for L in labs:
        for pre in ("B-","I-"):
            id2label[i]=pre+L; label2id[pre+L]=i; i+=1
    return labs,id2label,label2id
LABS,ID2,L2 = collect_labels([TRAIN,VAL])

def to_bio(text, spans):
    offs = tok(text, return_offsets_mapping=True, truncation=True, max_length=384)["offset_mapping"]
    labels=[0]*len(offs)
    for sp in spans:
        s,e,lab=sp["start"],sp["end"],sp["label"]
        # 給與任一重疊的 token 打標；開頭 token -> B-*, 後續 I-*
        started=False
        for i,(ts,te) in enumerate(offs):
            if te==0 and ts==0:   # special tokens
                continue
            if te<=s or ts>=e:    # no overlap
                continue
            tag=("B-"+lab) if not started else ("I-"+lab); started=True
            labels[i]=L2[tag]
    return labels, offs

def load_ds(path):
    xs=[]; 
    for ln in open(path,encoding="utf-8"):
        o=json.loads(ln); t=o["text"]; spans=o.get("spans",[])
        enc=tok(t, return_offsets_mapping=True, truncation=True, max_length=384)
        y,_ = to_bio(t, spans)
        # pad labels to input_ids length
        y = y[:len(enc["input_ids"])] + [0]*(len(enc["input_ids"])-len(y))
        xs.append({**{k:torch.tensor(v) for k,v in enc.items()}, "labels": torch.tensor(y)})
    return xs

train_ds = load_ds(TRAIN); val_ds = load_ds(VAL)
model = AutoModelForTokenClassification.from_pretrained(MODEL_NAME, num_labels=len(ID2), id2label=ID2, label2id=L2)
args = TrainingArguments(
    output_dir=os.path.join(OUTDIR,"_runs"),
    learning_rate=3e-5, per_device_train_batch_size=8, per_device_eval_batch_size=8,
    gradient_accumulation_steps=2, num_train_epochs=float(os.getenv("EPOCHS","3")),
    evaluation_strategy="epoch", save_strategy="epoch", save_total_limit=1,
    load_best_model_at_end=True, metric_for_best_model="f1", logging_steps=50, seed=SEED
)
def metrics(eval_pred):
    logits, labels = eval_pred
    preds = logits.argmax(-1)
    # 轉成詞級序列（去掉 special tokens=offset(0,0)）
    def to_tags(ids, lbls):
        tags_pred=[]; tags_true=[]
        for pi,li in zip(ids, lbls):
            pseq=[]; lseq=[]
            for p,l in zip(pi,li):
                pseq.append(ID2[int(p)]); lseq.append(ID2[int(l)])
            tags_pred.append([t for t in pseq if t!="O" or True])
            tags_true.append([t for t in lseq if t!="O" or True])
        return tags_pred, tags_true
    y_pred, y_true = to_tags(preds, labels)
    return {
        "precision": precision_score(y_true, y_pred),
        "recall":    recall_score(y_true, y_pred),
        "f1":        f1_score(y_true, y_pred),
    }
collator = DataCollatorForTokenClassification(tokenizer=tok)
trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds, data_collator=collator, tokenizer=tok, compute_metrics=metrics)
trainer.train()
model.save_pretrained(OUTDIR); tok.save_pretrained(OUTDIR)
print("[TRAIN] saved ->", OUTDIR)
PY
# env for python above
) 2>/dev/null || true; export OUTDIR="$OUTDIR" EPOCHS="$EPOCHS" SEED="$SEED"

# ---- 用剛訓練的模型在 GOLD 上評測（嚴格對齊 + 95%CI）----
[ -x sma_tools/kie_model_eval_pack.sh ] || { echo "[FATAL] missing sma_tools/kie_model_eval_pack.sh"; exit 95; }
sma_tools/kie_model_eval_pack.sh "$GOLD" --predictor xlmr --model-dir "$OUTDIR"

echo "[DONE] repair_and_train_kie completed. LOG=$LOG"

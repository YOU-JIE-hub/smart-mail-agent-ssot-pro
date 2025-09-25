#!/usr/bin/env bash
# .sma_tools/oneclick_train_eval_kie.sh
# 功能：自動銀標 → 訓練 → 推論 → 評測 → 模型卡（離線安全、零互動、可重跑）
# 用法：
#   .sma_tools/oneclick_train_eval_kie.sh \
#     --in-jsonl data/intent/i_merged.jsonl \
#     --silver   data/kie/silver.jsonl \
#     --model-dir artifacts/kie_xlmr \
#     --pred     reports_auto/kie_pred.jsonl \
#     --eval-gold data/kie/test.jsonl \
#     --epochs 3 --seed 42 \
#     --force-silver --force-train --force-eval
set -Eeuo pipefail
set -o errtrace
export PS4='+ [${BASH_SOURCE##*/}:${LINENO}] ► '
trap 'rc=$?; echo "[KIE][TRAP][ERR] line=$LINENO rc=$rc cmd=${BASH_COMMAND}"; exit $rc' ERR
trap 'echo "[KIE][TRAP][EXIT] rc=$?"' EXIT

ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
[ -d "$ROOT/.git" ] && [ -d "$ROOT/src" ] || { echo "[KIE][ERR] 非有效專案根：$ROOT"; exit 96; }
cd "$ROOT"

# 選擇 Python
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"
elif [ -x "$HOME/.venv/sma/bin/python" ]; then PY="$HOME/.venv/sma/bin/python"
else PY="$(command -v python3 || command -v python || true)"
fi
[ -n "$PY" ] || { echo "[KIE][ERR] 找不到 python"; exit 97; }

export PYTHONNOUSERSITE=1
export PYTHONPATH="$PWD:$(pwd)/src"
export OFFLINE="${OFFLINE:-1}"  # 預設離線
mkdir -p .sma_tools .sma_tools/logs reports_auto data/kie artifacts

LOG=".sma_tools/logs/kie_oneclick_$(date +%Y-%m-%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

# 預設值
IN_JSONL="data/intent/i_20250901_merged.jsonl"
SILVER_JSONL="data/kie/silver.jsonl"
MODEL_DIR="artifacts/kie_xlmr"
PRED_JSONL="reports_auto/kie_pred.jsonl"
GOLD_JSONL=""
EPOCHS=3
SEED=42
FORCE_SILVER=0
FORCE_TRAIN=0
FORCE_EVAL=0
BASE_MODEL="${SMA_KIE_BASE_MODEL:-xlm-roberta-base}"  # 若離線，請將此模型預先快取到 HF_HOME

# 參數解析
while [ $# -gt 0 ]; do
  case "$1" in
    --in-jsonl) IN_JSONL="$2"; shift 2;;
    --silver) SILVER_JSONL="$2"; shift 2;;
    --model-dir) MODEL_DIR="$2"; shift 2;;
    --pred) PRED_JSONL="$2"; shift 2;;
    --eval-gold) GOLD_JSONL="$2"; shift 2;;
    --epochs) EPOCHS="$2"; shift 2;;
    --seed) SEED="$2"; shift 2;;
    --force-silver) FORCE_SILVER=1; shift;;
    --force-train) FORCE_TRAIN=1; shift;;
    --force-eval) FORCE_EVAL=1; shift;;
    --base-model) BASE_MODEL="$2"; shift 2;;
    *) echo "[KIE][WARN] 忽略未知參數：$1"; shift;;
  esac
done

echo "[KIE][CONF] IN_JSONL=$IN_JSONL"
echo "[KIE][CONF] SILVER_JSONL=$SILVER_JSONL"
echo "[KIE][CONF] MODEL_DIR=$MODEL_DIR"
echo "[KIE][CONF] PRED_JSONL=$PRED_JSONL"
echo "[KIE][CONF] GOLD_JSONL=${GOLD_JSONL:-<none>}"
echo "[KIE][CONF] EPOCHS=$EPOCHS SEED=$SEED BASE_MODEL=$BASE_MODEL"
echo "[KIE][CONF] OFFLINE=$OFFLINE PY=$PY"

# 依賴檢查（不主動 pip install，避免聯網）
"$PY" - <<'PY'
import importlib, sys
mods = ["torch","transformers","seqeval","jinja2","numpy","scikit_learn"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    print("[KIE][ERR] 缺少套件：", ",".join(missing))
    print("[KIE][HINT] 請在本機 venv 安裝所需套件（離線環境請預先準備 wheel/caches）。")
    sys.exit(88)
print("[KIE][OK] 依賴檢查通過")
PY

# A) 自動銀標（若不存在或 --force-silver）
if [ "$FORCE_SILVER" -eq 1 ] || [ ! -s "$SILVER_JSONL" ]; then
  echo "[KIE][STEP] 產生銀標：$SILVER_JSONL"
  if [ -f ".sma_tools/generate_silver_kie.py" ]; then
    "$PY" -X faulthandler ".sma_tools/generate_silver_kie.py" \
      --in_jsonl "$IN_JSONL" \
      --out_jsonl "$SILVER_JSONL"
  else
    echo "[KIE][WARN] 找不到 .sma_tools/generate_silver_kie.py，使用內建簡易規則生成"
    "$PY" - <<'PY'
import json,sys,re,os
inp=os.environ.get("IN_JSONL","data/intent/i_20250901_merged.jsonl")
out=os.environ.get("SILVER_JSONL","data/kie/silver.jsonl")
os.makedirs(os.path.dirname(out),exist_ok=True)
pat_amount=re.compile(r'(?:NT\$|USD|\$)\s?\d[\d,]*(?:\.\d+)?')
pat_date=re.compile(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}/\d{1,2})')
def spans(text,rgx,label):
    out=[]
    for m in rgx.finditer(text):
        out.append({"start":m.start(),"end":m.end(),"label":label})
    return out
cnt=0
with open(inp,"r",encoding="utf-8") as fi, open(out,"w",encoding="utf-8") as fo:
    for line in fi:
        o=json.loads(line)
        t=o.get("text") or o.get("body") or ""
        s=[]
        s+=spans(t,pat_amount,"amount")
        s+=spans(t,pat_date,"date_time")
        fo.write(json.dumps({"text":t,"spans":s},ensure_ascii=False)+"\n")
        cnt+=1
print(f"[KIE][GEN_SILVER] wrote={cnt} -> {out}")
PY
  fi
else
  echo "[KIE][SKIP] 銀標已存在：$SILVER_JSONL"
fi

# B) 訓練（若不存在或 --force-train）
if [ "$FORCE_TRAIN" -eq 1 ] || [ ! -d "$MODEL_DIR" ] || [ ! -s "$MODEL_DIR/config.json" ]; then
  echo "[KIE][STEP] 訓練模型到：$MODEL_DIR"
  mkdir -p "$MODEL_DIR"
  HF_HOME="${HF_HOME:-${SMA_HF_HOME:-$HOME/.cache/huggingface}}"
  export HF_HOME
  echo "[KIE][CONF] HF_HOME=$HF_HOME"
  # 訓練實作：最小 HuggingFace Token Classification（BIO），依賴本地快取的 BASE_MODEL
  INP="$SILVER_JSONL" OUT="$MODEL_DIR" EPOCHS2="$EPOCHS" SEED2="$SEED" BASE="$BASE_MODEL" "$PY" - <<'PY'
import os,sys,json,random,math
from pathlib import Path
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification, get_linear_schedule_with_warmup
from torch.utils.data import Dataset, DataLoader
from seqeval.metrics import classification_report, f1_score

INP=os.environ["INP"]; OUT=os.environ["OUT"]
EPOCHS=int(os.environ.get("EPOCHS2","3")); SEED=int(os.environ.get("SEED2","42"))
BASE=os.environ.get("BASE","xlm-roberta-base")

def set_seed(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)

set_seed(SEED)
texts=[]; spans_list=[]
with open(INP,"r",encoding="utf-8") as f:
    for line in f:
        o=json.loads(line); texts.append(o["text"]); spans_list.append(o.get("spans",[]))

# 構建 BIO 標籤集
labels=set(["O"])
ent_types=sorted({s["label"] for sps in spans_list for s in sps})
for et in ent_types:
    labels.update({f"B-{et}",f"I-{et}"})
labels=sorted(labels)
label2id={l:i for i,l in enumerate(labels)}
id2label={i:l for l,i in label2id.items()}

tok=AutoTokenizer.from_pretrained(BASE)  # 需本地快取
def spans_to_bio(text,spans):
    bio=["O"]*len(text)
    for s in spans:
        st,ed,lb=s["start"],s["end"],s["label"]
        if st<0 or ed>len(text) or st>=ed: continue
        bio[st]=f"B-{lb}"
        for i in range(st+1,ed): bio[i]=f"I-{lb}"
    return bio

class KIEDS(Dataset):
    def __init__(self,texts,spans,train=True):
        self.texts=texts; self.spans=spans; self.train=train
    def __len__(self): return len(self.texts)
    def __getitem__(self,i):
        t=self.texts[i]; s=self.spans[i]
        enc=tok(list(t), is_split_into_words=True, return_offsets_mapping=True, truncation=True, padding=False, max_length=512)
        # 由字元 BIO 對應到 token label（simple alignment）
        char_bio=spans_to_bio(t,s)
        labels_ids=[]
        for (o_s,o_e) in enc["offset_mapping"]:
            if o_s==o_e: labels_ids.append(-100)
            else:
                tag=char_bio[o_s] if o_s<len(char_bio) else "O"
                labels_ids.append(label2id.get(tag, label2id["O"]))
        item={k: torch.tensor(v) for k,v in enc.items() if k!="offset_mapping"}
        item["labels"]=torch.tensor(labels_ids)
        return item

# 簡單切分 80/20
N=len(texts); idx=list(range(N)); random.shuffle(idx)
cut=int(N*0.8); tr_idx=idx[:cut]; va_idx=idx[cut:]
tr_ds=KIEDS([texts[i] for i in tr_idx],[spans_list[i] for i in tr_idx])
va_ds=KIEDS([texts[i] for i in va_idx],[spans_list[i] for i in va_idx])

model=AutoModelForTokenClassification.from_pretrained(BASE, num_labels=len(labels), id2label=id2label, label2id=label2id)
dev=torch.device("cuda" if torch.cuda.is_available() else "cpu"); model.to(dev)

def collate(batch):
    keys=batch[0].keys()
    out={k: torch.nn.utils.rnn.pad_sequence([b[k] for b in batch], batch_first=True, padding_value=0) for k in keys if k!="labels"}
    # labels padding 用 -100
    labs=[b["labels"] for b in batch]
    out["labels"]=torch.nn.utils.rnn.pad_sequence(labs, batch_first=True, padding_value=-100)
    return out

tr_dl=DataLoader(tr_ds,batch_size=8,shuffle=True,collate_fn=collate)
va_dl=DataLoader(va_ds,batch_size=8,shuffle=False,collate_fn=collate)

opt=torch.optim.AdamW(model.parameters(), lr=3e-5)
t_total=EPOCHS*len(tr_dl)
sch=get_linear_schedule_with_warmup(opt, num_warmup_steps=max(1,int(0.1*t_total)), num_training_steps=t_total)
loss_best=1e9

for ep in range(1,EPOCHS+1):
    model.train(); tl=0.0
    for b in tr_dl:
        b={k:v.to(dev) for k,v in b.items()}
        r=model(**b); loss=r.loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sch.step(); model.zero_grad(set_to_none=True)
        tl += loss.item()
    # 簡單 val f1（seqeval）
    model.eval(); y_true=[]; y_pred=[]
    with torch.no_grad():
        for b in va_dl:
            labels=b["labels"]
            b={k:v.to(dev) for k,v in b.items()}
            out=model(**b)
            preds=out.logits.argmax(-1).cpu().numpy()
            labs=labels.numpy()
            for p,l in zip(preds, labs):
                y_p=[]; y_l=[]
                for pi,li in zip(p,l):
                    if li==-100: continue
                    y_p.append(id2label[int(pi)])
                    y_l.append(id2label[int(li)])
                y_pred.append(y_p); y_true.append(y_l)
    f1=f1_score(y_true,y_pred)
    print(f"[KIE][TRAIN] epoch={ep} train_loss={tl/len(tr_dl):.4f} val_f1={f1:.4f}")
    if tl<loss_best: loss_best=tl
# 儲存
Path(OUT).mkdir(parents=True,exist_ok=True)
model.save_pretrained(OUT)
tok.save_pretrained(OUT)
with open(Path(OUT)/"labels.json","w",encoding="utf-8") as fo: json.dump({"labels":list(labels)},fo,ensure_ascii=False)
print(f"[KIE][SAVE] {OUT}")
PY
else
  echo "[KIE][SKIP] 模型已存在：$MODEL_DIR"
fi

# C) 推論（產生 PRED_JSONL；若有 .sma_tools/inference_kie.py 則優先用）
echo "[KIE][STEP] 推論 → $PRED_JSONL"
mkdir -p "$(dirname "$PRED_JSONL")"
if [ -f ".sma_tools/inference_kie.py" ]; then
  "$PY" -X faulthandler ".sma_tools/inference_kie.py" \
    --model_dir "$MODEL_DIR" \
    --in_jsonl  "$IN_JSONL" \
    --out_jsonl "$PRED_JSONL"
else
  echo "[KIE][WARN] 找不到 .sma_tools/inference_kie.py，使用內建最小推論"
  MODEL_DIR="$MODEL_DIR" IN_JSONL="$IN_JSONL" OUT_JSONL="$PRED_JSONL" "$PY" - <<'PY'
import os,json
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
md=os.environ["MODEL_DIR"]; inp=os.environ["IN_JSONL"]; out=os.environ["OUT_JSONL"]
tok=AutoTokenizer.from_pretrained(md); model=AutoModelForTokenClassification.from_pretrained(md)
dev=torch.device("cuda" if torch.cuda.is_available() else "cpu"); model.to(dev); model.eval()
Path(Path(out).parent).mkdir(parents=True,exist_ok=True)
def decode(text):
    enc=tok(list(text), is_split_into_words=True, return_offsets_mapping=True, return_tensors="pt", truncation=True, max_length=512)
    off=enc.pop("offset_mapping")[0].tolist()
    enc={k:v.to(dev) for k,v in enc.items()}
    with torch.no_grad():
        logits=model(**enc).logits[0].cpu()
    ids=logits.argmax(-1).tolist()
    # labels.json 提供映射
    import json as _json
    with open(f"{md}/labels.json","r",encoding="utf-8") as f: labs=_json.load(f)["labels"]
    spans=[]; cur=None
    for (s,e),lid in zip(off,ids):
        if s==e: continue
        lab=labs[lid]
        if lab=="O":
            if cur: spans.append(cur); cur=None
        else:
            tag,etype=lab.split("-",1)
            if tag=="B":
                if cur: spans.append(cur)
                cur={"start":s,"end":e,"label":etype}
            elif tag=="I":
                if cur and cur["label"]==etype: cur["end"]=e
                else: cur={"start":s,"end":e,"label":etype}
    if cur: spans.append(cur)
    return spans
n=0
with open(inp,"r",encoding="utf-8") as fi, open(out,"w",encoding="utf-8") as fo:
    for line in fi:
        o=json.loads(line); t=o.get("text") or o.get("body") or ""
        s=decode(t)
        fo.write(json.dumps({"text":t,"spans":s},ensure_ascii=False)+"\n"); n+=1
print(f"[KIE][PRED] wrote={n} -> {out}")
PY
fi

# D) 評測（若提供 GOLD_JSONL；可帶 --force-eval）
if [ -n "$GOLD_JSONL" ] && { [ "$FORCE_EVAL" -eq 1 ] || [ ! -s "reports_auto/kie_eval.txt" ]; }; then
  echo "[KIE][STEP] 評測 → reports_auto/kie_eval.txt"
  if [ -f ".sma_tools/eval_kie.py" ]; then
    "$PY" -X faulthandler ".sma_tools/eval_kie.py" \
      --pred "$PRED_JSONL" \
      --gold "$GOLD_JSONL" \
      --out  "reports_auto/kie_eval.txt"
  else
    echo "[KIE][WARN] 找不到 .sma_tools/eval_kie.py，使用內建最小評測（strict span match）"
    PRED="$PRED_JSONL" GOLD="$GOLD_JSONL" "$PY" - <<'PY'
import json,sys
from pathlib import Path
pred=sys.argv[1] if len(sys.argv)>1 else None
gold=sys.argv[2] if len(sys.argv)>2 else None
pred=pred or "reports_auto/kie_pred.jsonl"; gold=gold or "data/kie/test.jsonl"
def load(p):
    arr=[]; 
    with open(p,"r",encoding="utf-8") as f:
        for ln in f: arr.append(json.loads(ln))
    return arr
P=load(pred); G=load(gold)
tp=fp=fn=0
for p,g in zip(P,G):
    ps={(s["start"],s["end"],s["label"]) for s in p.get("spans",[])}
    gs={(s["start"],s["end"],s["label"]) for s in g.get("spans",[])}
    tp+=len(ps&gs); fp+=len(ps-gs); fn+=len(gs-ps)
prec=tp/(tp+fp) if (tp+fp)>0 else 0.0
rec =tp/(tp+fn) if (tp+fn)>0 else 0.0
f1  =2*prec*rec/(prec+rec) if (prec+rec)>0 else 0.0
out="reports_auto/kie_eval.txt"
Path("reports_auto").mkdir(parents=True,exist_ok=True)
with open(out,"w",encoding="utf-8") as fo:
    fo.write(f"strict_span_P={prec:.4f}\nstrict_span_R={rec:.4f}\nstrict_span_F1={f1:.4f}\n")
print(f"[KIE][EVAL] -> {out}")
PY
  fi
else
  if [ -z "$GOLD_JSONL" ]; then
    echo "[KIE][SKIP] 未提供 --eval-gold，略過評測"
  else
    echo "[KIE][SKIP] 已存在 reports_auto/kie_eval.txt（可用 --force-eval 重算）"
  fi
fi

# E) 模型卡（整合基本資訊）
echo "[KIE][STEP] 生成模型卡 → reports_auto/model_card_kie.md"
ENV_INP="$IN_JSONL" ENV_SILV="$SILVER_JSONL" ENV_PRED="$PRED_JSONL" ENV_MD="$MODEL_DIR" "$PY" - <<'PY'
import os, json, time, pathlib
card = pathlib.Path("reports_auto/model_card_kie.md")
card.parent.mkdir(parents=True, exist_ok=True)
eval_txt = pathlib.Path("reports_auto/kie_eval.txt")
metrics = {}
if eval_txt.exists():
    for ln in eval_txt.read_text(encoding="utf-8").splitlines():
        if "=" in ln:
            k,v=ln.split("=",1); metrics[k.strip()]=v.strip()
ts=time.strftime("%Y-%m-%d %H:%M:%S")
body=f"""# KIE Model Card

- Timestamp: {ts}
- Base Model: {os.environ.get("SMA_KIE_BASE_MODEL","xlm-roberta-base")}
- Input JSONL: {os.environ.get("ENV_INP")}
- Silver JSONL: {os.environ.get("ENV_SILV")}
- Pred JSONL: {os.environ.get("ENV_PRED")}
- Model Dir: {os.environ.get("ENV_MD")}

## Metrics (strict span)
{json.dumps(metrics, ensure_ascii=False, indent=2)}

## Notes
- 離線訓練；如需復現請確認 HF_HOME 內已快取 base model。
- 若要重算銀標/訓練/評測：加上 --force-silver / --force-train / --force-eval。
"""
card.write_text(body, encoding="utf-8")
print(f"[KIE][CARD] -> {card}")
PY

echo "[KIE][DONE] 全流程完成。主要產物："
echo " - 模型：$MODEL_DIR"
echo " - 推論：$PRED_JSONL"
echo " - 評測：reports_auto/kie_eval.txt（若提供 --eval-gold）"
echo " - 模型卡：reports_auto/model_card_kie.md"
echo " - 日誌：$LOG"

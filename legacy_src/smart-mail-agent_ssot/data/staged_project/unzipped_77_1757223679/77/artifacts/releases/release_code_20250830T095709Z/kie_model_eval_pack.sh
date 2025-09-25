#!/usr/bin/env bash
set -Eeuo pipefail; set -o errtrace; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"; cd "$ROOT" || exit 96
[ -f ".venv/bin/activate" ] && source .venv/bin/activate 2>/dev/null || true

usage(){ echo "Usage: $0 <gold_jsonl> [--predictor regex|xlmr] [--model-dir artifacts/kie_xlmr]"; }
[ $# -ge 1 ] || { usage; exit 2; }
GOLD="$1"; shift
PREDICTOR="regex"; MODEL_DIR="artifacts/kie_xlmr"
while [ $# -gt 0 ]; do
  case "$1" in
    --predictor) PREDICTOR="$2"; shift 2;;
    --model-dir) MODEL_DIR="$2"; shift 2;;
    *) echo "[WARN] unknown arg: $1"; shift;;
  esac
done

[ -s "$GOLD" ] || { echo "[FATAL] gold not found or empty: $GOLD"; exit 91; }
mkdir -p reports_auto data/kie

PRED="reports_auto/kie_pred.jsonl"
EVAL="reports_auto/kie_eval.txt"
CI="reports_auto/kie_eval_ci.txt"
CMP="reports_auto/kie_model_vs_rule.txt"

echo "[INFO] GOLD=$GOLD"
echo "[INFO] PREDICTOR=$PREDICTOR"

# 1) 產 PRED（嚴格以 GOLD 作為輸入）
case "$PREDICTOR" in
  regex)
    [ -x sma_tools/kie_regex_min.sh ] || { echo "[FATAL] missing sma_tools/kie_regex_min.sh"; exit 92; }
    sma_tools/kie_regex_min.sh "$GOLD"
    ;;
  xlmr)
    # 推論器（最小可用）：用 HF 已訓練模型對 GOLD 做 token-classification，輸出 spans
    # 若你已經有專屬推論腳本，改成你的即可；重點是「輸入=GOLD」
    python - "$@" <<'PY'
import json, sys, re
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
MODEL="artifacts/kie_xlmr"
IN=sys.argv[-1] if sys.argv[-1].endswith(".jsonl") else "data/intent/test.jsonl"
OUT="reports_auto/kie_pred.jsonl"
tok=AutoTokenizer.from_pretrained(MODEL)
mdl=AutoModelForTokenClassification.from_pretrained(MODEL)
lbl=mdl.config.id2label
def decode_spans(text, ids, offs):
    spans=[]; open_tag=None
    for i,(id,(s,e)) in enumerate(zip(ids,offs)):
        tag=lbl.get(int(id),"O")
        if tag.startswith("B-"):
            if open_tag: spans.append(open_tag)
            open_tag={"start":s,"end":e,"label":tag[2:]}
        elif tag.startswith("I-"):
            if open_tag and open_tag["label"]==tag[2:]:
                open_tag["end"]=e
            else:
                open_tag={"start":s,"end":e,"label":tag[2:]}
        else:
            if open_tag: spans.append(open_tag); open_tag=None
    if open_tag: spans.append(open_tag)
    return spans
with open(IN,encoding="utf-8") as fi, open(OUT,"w",encoding="utf-8") as fo:
    for ln in fi:
        o=json.loads(ln); t=o.get("text","")
        enc=tok(t, return_offsets_mapping=True, truncation=True, max_length=384, return_tensors="pt")
        with torch.no_grad():
            logits=mdl(**{k:v for k,v in enc.items() if k!="offset_mapping"}).logits[0]
        ids=logits.argmax(-1).tolist()
        offs=[(int(s),int(e)) for (s,e) in enc["offset_mapping"][0].tolist()]
        # 去掉 special tokens 的 offset
        keep=[(i,(s,e),ids[i]) for i,(s,e) in enumerate(offs) if s!=0 or e!=0]
        ids=[k for _,_,k in keep]; offs=[(s,e) for _,(s,e),_ in keep]
        spans=decode_spans(t, ids, offs)
        fo.write(json.dumps({"text":t,"spans":spans},ensure_ascii=False)+"\n")
print("[OK] model inference -> reports_auto/kie_pred.jsonl")
PY
    python - <<'PY'
import sys; print("[CHECK] pred_lines=", sum(1 for _ in open("reports_auto/kie_pred.jsonl","r",encoding="utf-8")))
PY
    ;;
  *)
    echo "[FATAL] unknown predictor: $PREDICTOR"; exit 93;;
esac

# 2) 嚴格評測（文本+出現次序對齊）
python sma_tools/kie_eval_full.py "$PRED" "$GOLD" "$EVAL" || { echo "[FATAL] eval failed"; exit 94; }
echo "[EVAL] -> $EVAL"

# 3) 95% CI（bootstrap over pairs）
[ -f sma_tools/kie_eval_ci.py ] && python sma_tools/kie_eval_ci.py "$PRED" "$GOLD" "$CI" && echo "[CI] -> $CI" || echo "[CI] skipped (no script)"

# 4) 更新模型卡（保留原有欄位）
[ -x sma_tools/kie_write_model_card.sh ] && sma_tools/kie_write_model_card.sh || true

echo "[DONE] model_eval_pack"

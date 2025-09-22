#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODEL_DIR="$HERE/model"

echo "[INFO] model dir: $MODEL_DIR"
python - <<PY
from pathlib import Path
print(Path("$HERE/kie_model_dump.txt").read_text())
PY

# 若打包中有官方腳本就用；沒有則只做 forward sanity
if [[ -f "$HERE/tools/_pred_xlmr_snap.py" && -f "$HERE/tools/_eval_occ.py" ]]; then
  IN="${1:-$HERE/data/kie/test_real.jsonl}"
  if [[ -f "$IN" ]]; then
    echo "[RUN] pred -> eval on: $IN"
    python "$HERE/tools/_pred_xlmr_snap.py" "$IN" "$MODEL_DIR" "$HERE/kie_preds.jsonl"
    python "$HERE/tools/_eval_occ.py"      "$HERE/kie_preds.jsonl" "$IN" "$HERE/kie_eval.txt"
    sed -n '1,120p' "$HERE/kie_eval.txt"
  else
    echo "[WARN] 找不到測試集（$IN），僅做 forward 檢查"
    python - <<'PY'
from transformers import AutoTokenizer, AutoModelForTokenClassification
from pathlib import Path
d=Path("model")
tok=AutoTokenizer.from_pretrained(d, use_fast=True)
mdl=AutoModelForTokenClassification.from_pretrained(d)
enc=tok("This is a quick sanity forward.", return_tensors="pt")
print("[SANITY] logits", tuple(mdl(**enc).logits.shape))
PY
  fi
else
  echo "[WARN] tools 不齊，僅做 forward 檢查"
  python - <<'PY'
from transformers import AutoTokenizer, AutoModelForTokenClassification
from pathlib import Path
d=Path("model")
tok=AutoTokenizer.from_pretrained(d, use_fast=True)
mdl=AutoModelForTokenClassification.from_pretrained(d)
enc=tok("This is a quick sanity forward.", return_tensors="pt")
print("[SANITY] logits", tuple(mdl(**enc).logits.shape))
PY
fi

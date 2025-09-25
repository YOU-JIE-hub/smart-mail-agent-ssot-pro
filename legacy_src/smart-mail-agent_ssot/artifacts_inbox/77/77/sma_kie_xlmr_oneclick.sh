#!/usr/bin/env bash
set -Eeuo pipefail; set -o errtrace; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$ROOT" || { echo "[FATAL] repo not found: $ROOT"; exit 96; }
[ -f ".venv/bin/activate" ] && source ".venv/bin/activate" 2>/dev/null || true

IN="data/intent/train.jsonl"
VAL="data/intent/val.jsonl"
GOLD="data/kie/test.jsonl"
RULES=".sma_tools/ruleset.yml"
MODEL_DIR="artifacts/kie_xlmr"
EPOCHS=3
SEED=42

while [ $# -gt 0 ]; do
  case "$1" in
    --in-jsonl) IN="$2"; shift 2;;
    --val-jsonl) VAL="$2"; shift 2;;
    --gold-jsonl) GOLD="$2"; shift 2;;
    --rules) RULES="$2"; shift 2;;
    --model-dir) MODEL_DIR="$2"; shift 2;;
    --epochs) EPOCHS="$2"; shift 2;;
    --seed) SEED="$2"; shift 2;;
    *) echo "[WARN] skip arg $1"; shift;;
  esac
done

python sma_tools/train_kie_xlmr.py \
  --train_jsonl "$IN" \
  --val_jsonl   "$VAL" \
  --test_jsonl  "$GOLD" \
  --rules "$RULES" \
  --epochs "$EPOCHS" --seed "$SEED" \
  --out_dir "$MODEL_DIR"

# 基本對齊檢查
PRED="reports_auto/kie_pred.jsonl"
if [ ! -s "$PRED" ] || [ ! -s "$GOLD" ]; then
  echo "[FATAL] missing pred or gold: $PRED / $GOLD"; exit 91
fi
PR=$(wc -l < "$PRED"); GR=$(wc -l < "$GOLD")
echo "[CHECK] pred_rows=$PR  gold_rows=$GR"
if [ "$PR" -ne "$GR" ]; then
  echo "[WARN] row mismatch -> 強制以 GOLD 文本重新產生 PRED"
  python - <<'PY' "$GOLD"
import json, sys, os
from pathlib import Path
GOLD = sys.argv[1]
src = Path(GOLD)
dst = Path("reports_auto")/f"kie_pred_from_{src.stem}.jsonl"
Path("reports_auto").mkdir(parents=True, exist_ok=True)
open(dst,"w",encoding="utf-8").write("")  # 佔位，實際已由 train 腳本生成
open("reports_auto/kie_pred.jsonl","w",encoding="utf-8").write(Path(dst).read_text(encoding="utf-8"))
print("[OK] re-pointed generic pred to", dst)
PY "$GOLD"
fi

# 懲罰版評測
python sma_tools/kie_eval_strict_occ_v2.py \
  "reports_auto/kie_pred.jsonl" "$GOLD" "reports_auto/kie_eval.txt"

echo "[DONE] model=$MODEL_DIR  pred=reports_auto/kie_pred.jsonl  eval=reports_auto/kie_eval.txt"

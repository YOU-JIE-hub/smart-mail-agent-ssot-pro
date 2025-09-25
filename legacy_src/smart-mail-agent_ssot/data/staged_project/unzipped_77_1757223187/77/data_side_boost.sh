#!/usr/bin/env bash
set -Eeuo pipefail; set -o errtrace; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$ROOT" || { echo "[FATAL] repo not found: $ROOT"; exit 96; }
[ -f ".venv/bin/activate" ] && source ".venv/bin/activate" 2>/dev/null || true

IN_T="data/intent/train.jsonl"; IN_V="data/intent/val.jsonl"; TEST="data/intent/test.jsonl"
OUT_T="data/intent/train_aug.jsonl"; OUT_V="data/intent/val_aug.jsonl"
SIL_T="data/kie/silver_train.jsonl"; SIL_V="data/kie/silver_val.jsonl"
QUEUE="data/kie/label_queue.jsonl"; MANI="reports_auto/dataset_manifest.json"

echo "[STEP] augment train/val -> *_aug.jsonl"
python sma_tools/augment_intent_texts.py --in_jsonl "$IN_T" --out_jsonl "$OUT_T" --ratio 0.5
python sma_tools/augment_intent_texts.py --in_jsonl "$IN_V" --out_jsonl "$OUT_V" --ratio 0.5

echo "[STEP] silver by rules -> data/kie/silver_{train,val}.jsonl"
python sma_tools/gen_silver_from_rules.py --in_jsonl "$OUT_T" --out_jsonl "$SIL_T"
python sma_tools/gen_silver_from_rules.py --in_jsonl "$OUT_V" --out_jsonl "$SIL_V"

echo "[STEP] weekly label queue (25%) -> $QUEUE"
python sma_tools/prepare_label_queue.py --in_jsonl "$OUT_T" --out_jsonl "$QUEUE" --ratio 0.25

echo "[STEP] dataset manifest (SHA) -> $MANI"
python sma_tools/dataset_manifest.py --train "$OUT_T" --val "$OUT_V" --test "$TEST" --out "$MANI"

echo "[OK] data-side boost complete."
echo "[HINT] train with: sma_tools/sma_kie_xlmr_oneclick.sh --in-jsonl $OUT_T --val-jsonl $OUT_V --gold-jsonl data/kie/test.jsonl"

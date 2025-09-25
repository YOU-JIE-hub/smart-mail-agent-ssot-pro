#!/usr/bin/env bash
set -Eeuo pipefail; set -o errtrace; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"; cd "$ROOT" || exit 96
[ -f ".venv/bin/activate" ] && source .venv/bin/activate 2>/dev/null || true
mkdir -p .sma_logs reports_auto artifacts/kie_xlmr data/kie

# ---- args ----
TRAIN="data/intent/train_aug.jsonl"
VAL="data/intent/val_aug.jsonl"
GOLD="data/kie/test_real.jsonl"
OUTDIR="artifacts/kie_xlmr"
EPOCHS=3; SEED=42
while [ $# -gt 0 ]; do
  case "$1" in
    --train) TRAIN="$2"; shift 2;;
    --val)   VAL="$2"; shift 2;;
    --gold)  GOLD="$2"; shift 2;;
    --out)   OUTDIR="$2"; shift 2;;
    --epochs) EPOCHS="$2"; shift 2;;
    --seed)   SEED="$2"; shift 2;;
    *) echo "[WARN] unknown arg: $1"; shift;;
  esac
done

TS="$(date +%Y-%m-%d_%H%M%S)"; LOG=".sma_logs/kie_train_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "[INFO] TRAIN=$TRAIN"; echo "[INFO] VAL=$VAL"; echo "[INFO] GOLD=$GOLD"; echo "[INFO] OUTDIR=$OUTDIR"
[ -s "$TRAIN" ] || { echo "[FATAL] train not found: $TRAIN"; exit 91; }
[ -s "$VAL" ]   || { echo "[FATAL] val not found: $VAL"; exit 92; }
[ -s "$GOLD" ]  || { echo "[FATAL] gold not found: $GOLD"; exit 93; }
[ -s ".sma_tools/ruleset.yml" ] || { echo "[FATAL] missing .sma_tools/ruleset.yml"; exit 94; }

# 如果 OUTDIR 是 regex_stub 佔位 → 先備份清空
if [ -f "$OUTDIR/config.json" ] && grep -q '"model_type"[[:space:]]*:[[:space:]]*"regex_stub"' "$OUTDIR/config.json"; then
  BAK="${OUTDIR}.stub.${TS}"; echo "[WARN] regex_stub detected → backup to $BAK & clear $OUTDIR"
  mkdir -p "$BAK"; cp -a "$OUTDIR"/. "$BAK"/; rm -rf "$OUTDIR"/* || true
fi

# ---- 1) 產銀標 ----
SILV_T="data/kie/silver_train.jsonl"
SILV_V="data/kie/silver_val.jsonl"
python sma_tools/silver_from_rules.py "$TRAIN" "$SILV_T" ".sma_tools/ruleset.yml"
python sma_tools/silver_from_rules.py "$VAL"   "$SILV_V" ".sma_tools/ruleset.yml"

# ---- 2) 訓練 ----
python sma_tools/train_xlmr_from_silver.py \
  --silver_train "$SILV_T" --silver_val "$SILV_V" \
  --outdir "$OUTDIR" --epochs "$EPOCHS" --seed "$SEED"

# ---- 3) GOLD 上推論 ----
PRED="reports_auto/kie_pred.jsonl"
python sma_tools/predict_spans_xlmr.py "$GOLD" "$OUTDIR" "$PRED"

# ---- 4) 評測 + 95% CI ----
python sma_tools/kie_eval_full.py "$PRED" "$GOLD" "reports_auto/kie_eval.txt" || true
if [ -f "sma_tools/kie_eval_ci.py" ]; then
  python sma_tools/kie_eval_ci.py "$PRED" "$GOLD" "reports_auto/kie_eval_ci.txt" && echo "[CI] -> reports_auto/kie_eval_ci.txt"
fi

echo "[DONE] all ok. LOG=$LOG"

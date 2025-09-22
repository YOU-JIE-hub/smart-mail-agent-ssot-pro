#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"; cd "$ROOT"
PY="${PY:-$(command -v python3 || command -v python)}"; : "${PY:?python not found}"

IN="data/intent/i_demo.jsonl"
SILV="data/kie/silver.jsonl"
MD="artifacts/kie_xlmr"
PRED="reports_auto/kie_pred.jsonl"
GOLD=""
EPOCHS=3
SEED=42
BASE="xlm-roberta-base"
MAXLEN=512

while [ $# -gt 0 ]; do
  case "$1" in
    --in-jsonl) IN="$2"; shift 2;;
    --silver) SILV="$2"; shift 2;;
    --model-dir) MD="$2"; shift 2;;
    --pred) PRED="$2"; shift 2;;
    --eval-gold) GOLD="$2"; shift 2;;
    --epochs) EPOCHS="$2"; shift 2;;
    --seed) SEED="$2"; shift 2;;
    --base) BASE="$2"; shift 2;;
    --max-len) MAXLEN="$2"; shift 2;;
    *) echo "[WARN] ignore $1"; shift;;
  esac
done

mkdir -p "$(dirname "$SILV")" "$(dirname "$PRED")" "$MD" reports_auto .sma_tools

[ -s ".sma_tools/ruleset.yml" ] || { echo "[ERR] 缺少 .sma_tools/ruleset.yml"; exit 90; }

echo "[1/4] 生成銀標";   "$PY" .sma_tools/generate_silver_kie.py --in_jsonl "$IN" --out_jsonl "$SILV" --rules ".sma_tools/ruleset.yml"
echo "[2/4] 訓練模型";   "$PY" .sma_tools/train_kie.py            --silver "$SILV" --model_dir "$MD" --base_model "$BASE" --epochs "$EPOCHS" --seed "$SEED" --max_len "$MAXLEN"
echo "[3/4] 推論輸出";   "$PY" .sma_tools/inference_kie.py        --model_dir "$MD" --in_jsonl "$IN" --out_jsonl "$PRED" --max_len "$MAXLEN"
if [ -n "${GOLD:-}" ] && [ -s "$GOLD" ]; then
  echo "[4/4] 評測 F1"; "$PY" .sma_tools/eval_kie.py              --pred "$PRED" --gold "$GOLD" --model_dir "$MD" --out "reports_auto/kie_eval.txt" --max_len "$MAXLEN"
else
  echo "[4/4] 略過評測（未提供 --eval-gold 或檔案不存在）"
fi
echo "[DONE] 產物：$MD / $PRED / reports_auto/kie_eval.txt(如有)"

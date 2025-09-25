#!/usr/bin/env bash
set -Eeuo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -f "$here/kie/pytorch_model.bin" && ! -f "$here/kie/model.safetensors" ]]; then
  echo "[FATAL] 權重未就緒。請依 PLACE_WEIGHTS_HERE.txt 提示將原始權重放到 $here/kie/"; exit 86;
fi
if [[ -z "${1:-}" || ! -f "$1" ]]; then
  echo "用法：bash RUNME_kie.sh <text_or_jsonl_path> [gold.jsonl]"; exit 0;
fi
python "$here/RUNME_kie_demo.py" --model_dir "$here/kie" --input "$1" --out "$here/pred_kie.tsv"
echo "[INFO] 預測輸出 -> $here/pred_kie.tsv"
if [[ -n "${2:-}" && -f "$2" ]]; then
  python "$here/RUNME_kie_eval.py" --gold "$2" --pred "$here/pred_kie.tsv"
fi

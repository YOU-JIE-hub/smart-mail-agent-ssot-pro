#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

# Demo 1：對一個純文字檔（每行一封）抽取
if [[ -f "$1" ]]; then
  IN="$1"
else
  echo "用法：bash RUNME_kie.sh <text_or_jsonl_path>"
  echo "範例：bash RUNME_kie.sh sample.jsonl"
  exit 0
fi

python "$here/RUNME_kie_demo.py" --model_dir "$here/kie" --input "$IN" --out "$here/pred_kie.tsv"
echo "[INFO] 預測輸出 -> $here/pred_kie.tsv"

# 若同時有金標 jsonl，就順便 eval
if [[ "${2:-}" != "" && -f "$2" ]]; then
  python "$here/RUNME_kie_eval.py" --gold "$2" --pred "$here/pred_kie.tsv"
fi

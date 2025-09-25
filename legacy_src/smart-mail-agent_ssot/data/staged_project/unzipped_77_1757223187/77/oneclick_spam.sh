#!/usr/bin/env bash
source .sma_tools/env_guard.sh
set -Eeuo pipefail
ROOT="$(pwd)"
TR="${1:-data/prod_merged/train.jsonl}"
VA="${2:-data/prod_merged/val.jsonl}"
TE="${3:-data/prod_merged/test.jsonl}"

# 後備：若 prod_merged 不存在，回退到 spam_sa / trec06c_zip
[[ -s "$TR" ]] || TR="data/spam_sa/train.jsonl"
[[ -s "$VA" ]] || VA="data/spam_sa/val.jsonl"
[[ -s "$TE" ]] || TE="data/spam_sa/test.jsonl"
[[ -s "$TR" ]] || TR="data/trec06c_zip/train.jsonl"
[[ -s "$VA" ]] || VA="data/trec06c_zip/val.jsonl"
[[ -s "$TE" ]] || TE="data/trec06c_zip/test.jsonl"

echo "[DATA] train=$TR"; echo "[DATA] val=$VA"; echo "[DATA] test=$TE"
if [[ ! -s "$TR" || ! -s "$VA" || ! -s "$TE" ]]; then
  echo "[FATAL] no dataset found."
  echo "  expected any of:"
  echo "    data/prod_merged/{train,val,test}.jsonl  OR"
  echo "    data/spam_sa/{train,val,test}.jsonl      OR"
  echo "    data/trec06c_zip/{train,val,test}.jsonl"
  echo "  Fix: generate datasets (scripts/sa_split.py / zip2jsonl_trec06c.py) or place files and rerun."
  exit 86
fi

python scripts/spam_train.py --train "$TR" --val "$VA" --out_dir artifacts_prod
python scripts/spam_sweep_thresholds.py --val "$VA" --model_dir artifacts_prod --out_dir artifacts_prod --out_reports reports_auto
python scripts/sma_quick_eval.py --test "$TE" --model_dir artifacts_prod --out reports_auto/prod_quick_report.md

# 打 release 記錄與時間戳
ts=$(date -u +%Y%m%dT%H%M%SZ)
rel="artifacts/releases/spam/${ts}-spam-textlr"
mkdir -p "$rel"
cp -f artifacts_prod/model_pipeline.pkl "$rel/"
cp -f artifacts_prod/text_lr_platt.pkl "$rel/" || true
cp -f artifacts_prod/ens_thresholds.json "$rel/"
printf "%s\n" "$rel" > artifacts/releases/spam/current_dir.txt

# Model Card（環境+指標）
python - <<PY
from pathlib import Path
import json, numpy, sklearn, platform
card={
 "timestamp":"$ts",
 "release_dir":"$rel",
 "train":"$TR","val":"$VA","test":"$TE",
 "artifacts":{"model_pipeline":"$rel/model_pipeline.pkl","thresholds":"$rel/ens_thresholds.json"},
 "metrics_md":"reports_auto/prod_quick_report.md",
 "env":{"python":platform.python_version(),"numpy":numpy.__version__,"sklearn":sklearn.__version__}
}
Path("model_card_spam.md").write_text("# Spam Model Card\\n\\n"+json.dumps(card,ensure_ascii=False,indent=2),encoding="utf-8")
print("[CARD] model_card_spam.md")
PY

echo "[DONE] Spam release -> $rel"
echo "[TIP ] Run: scripts/sma_infer_eml.py <eml_path_or_dir> --model_dir artifacts_prod --out reports_auto/predict_eml.tsv"

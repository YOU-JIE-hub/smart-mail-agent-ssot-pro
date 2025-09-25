#!/usr/bin/env bash
source .sma_tools/env_guard.sh
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/.sma_tools/env_guard.sh"

EML="${1:-}"; [[ -z "$EML" ]] && { echo "用法：$0 /path/to/eml_or_dir"; exit 2; }

# 權重檢查
test -f artifacts_prod/model_pipeline.pkl   || { echo "[FATAL] 缺 spam 權重 artifacts_prod/model_pipeline.pkl"; exit 91; }
test -f artifacts_prod/ens_thresholds.json  || { echo "[FATAL] 缺 spam 門檻 artifacts_prod/ens_thresholds.json"; exit 92; }
test -f artifacts/intent_pro_cal.pkl        || { echo "[FATAL] 缺 intent 權重 artifacts/intent_pro_cal.pkl"; exit 93; }
test -f reports_auto/intent_thresholds.json || { echo "[FATAL] 缺 intent 門檻 reports_auto/intent_thresholds.json"; exit 94; }

KIE_DIR=""
for d in "kie" "reports_auto/kie/kie"; do
  if [[ -f "$d/model.safetensors" || -f "$d/pytorch_model.bin" ]]; then KIE_DIR="$d"; break; fi
done
[[ -z "$KIE_DIR" ]] && { echo "[FATAL] 找不到 KIE 權重（kie/ 或 reports_auto/kie/kie/）"; exit 95; }

STAMP="$(date +%Y%m%d-%H%M%S)"
OUTDIR="$ROOT/reports_auto/e2e_mail/${STAMP}"
mkdir -p "$OUTDIR" "$ROOT/reports_auto/_tmp_e2e"

# A) 讀信
python "$ROOT/scripts/sma_ingest_eml.py" --input "$EML" --out "$OUTDIR/cases.jsonl"

# B) 三模型 + 決策（含 fields）
python "$ROOT/scripts/sma_e2e_run.py" \
  --cases "$OUTDIR/cases.jsonl" \
  --kie_dir "$KIE_DIR" \
  --out_dir "$OUTDIR" \
  2>&1 | tee "$OUTDIR/e2e_mail.log"

# C) RPA out（emit-sh：輸出可直接跑的腳本）
python "$ROOT/scripts/sma_actions_exec.py" \
  --cases "$OUTDIR/cases.jsonl" \
  --in_actions "$OUTDIR/actions.jsonl" \
  --out_dir "$OUTDIR/rpa_out" \
  --mode emit-sh

echo "[OK] 完成。報表：$OUTDIR/SUMMARY.md"

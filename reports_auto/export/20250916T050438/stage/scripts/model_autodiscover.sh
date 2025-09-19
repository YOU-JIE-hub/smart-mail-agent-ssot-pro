#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
OUT="reports_auto/model_autodiscover"; mkdir -p "$OUT"
LOG="$OUT/$(date +%Y%m%dT%H%M%S).log"; exec > >(tee -a "$LOG") 2>&1
CANDS=()
push(){ [ -f "$1" ] && CANDS+=("$1"); }
# 既有環境變數優先
[ -n "${SMA_INTENT_ML_PKL:-}" ] && push "$SMA_INTENT_ML_PKL"
# 常見位置
push artifacts/intent_pipeline_aligned.pkl
for p in artifacts/intent_*.pkl intent/**/artifacts/intent_pro_cal.pkl intent/**/artifacts/intent_pipeline*.pkl smart-mail-agent*/artifacts/releases/intent/*/intent_*.pkl; do
  for f in $p; do [ -f "$f" ] && CANDS+=("$f"); done
done
if [ "${#CANDS[@]}" -eq 0 ]; then
  REQ="$OUT/REQUEST_missing_model.md"
  {
    echo "# REQUEST: 缺少意圖分類模型 PKL"
    echo "- 期望變數：SMA_INTENT_ML_PKL（指向可讀的 .pkl）"
    echo "- 推薦放置：artifacts/intent_pipeline_aligned.pkl"
    echo "- 你也可以丟到任意路徑，然後執行："
    echo "  export SMA_INTENT_ML_PKL=\"/abs/path/to/your_model.pkl\""
    echo "- 完成後重跑：scripts/tri_eval_all.sh"
  } > "$REQ"
  echo "[FATAL] 沒找到任何 .pkl；已產說明：$REQ"
  exit 2
fi
BEST="${CANDS[0]}"
mkdir -p scripts
if [ ! -f scripts/env.default ]; then
  cat > scripts/env.default <<'ENV'
SMA_DRY_RUN=1
SMA_LLM_PROVIDER=none
SMA_EML_DIR=fixtures/eml
SMA_INTENT_ML_PKL=
ENV
fi
if grep -q '^SMA_INTENT_ML_PKL=' scripts/env.default; then
  sed -i "s|^SMA_INTENT_ML_PKL=.*|SMA_INTENT_ML_PKL=${BEST}|" scripts/env.default
else
  echo "SMA_INTENT_ML_PKL=${BEST}" >> scripts/env.default
fi
echo "[OK] SMA_INTENT_ML_PKL -> ${BEST}"

#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"; RUN="reports_auto/train_swap/${TS}"; mkdir -p "$RUN" reports_auto/status
LOG="$RUN/run.log"; ERR="$RUN/train_swap.err"
exec > >(tee -a "$LOG") 2>&1
trap 'echo "exit_code=$?" >"$ERR"; echo "[ERR] see: $(cd "$RUN"&&pwd)/train_swap.err"; exit 1' ERR
echo "[*] retrain+swap TS=$TS"

# 0) venv（沿用兄弟專案）
[ -e .venv ] || { [ -d /home/youjie/projects/smart-mail-agent_ssot/.venv ] && ln -s /home/youjie/projects/smart-mail-agent_ssot/.venv .venv || true; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
PYBIN="./.venv/bin/python"; command -v $PYBIN >/dev/null || PYBIN="$(command -v python)"

# 1) 訓練（輸入資料固定用你的 jsonl）
OUT_PKL="artifacts/intent_pipeline_aligned.pkl"
$PYBIN scripts/train_intent_min.py "data/intent_eval/dataset.cleaned.jsonl" "$OUT_PKL"
echo "$OUT_PKL" > "$RUN/new_model.txt"

# 2) 切換 env.default 的 ML 路徑（不動其他變數）
if [ -f scripts/env.default ]; then
  awk -v m="$(cd "$(dirname "$OUT_PKL")" && pwd)/$(basename "$OUT_PKL")" '
    BEGIN{sm=0}
    /^SMA_INTENT_ML_PKL=/{print "SMA_INTENT_ML_PKL=" m; sm=1; next}
    {print}
    END{if(!sm) print "SMA_INTENT_ML_PKL=" m}
  ' scripts/env.default > scripts/.env.tmp && mv scripts/.env.tmp scripts/env.default
else
  cat > scripts/env.default <<ENV
SMA_DRY_RUN=1
SMA_LLM_PROVIDER=none
SMA_EML_DIR=fixtures/eml
SMA_INTENT_ML_PKL=$(cd "$(dirname "$OUT_PKL")" && pwd)/$(basename "$OUT_PKL")
PORT=8000
ENV
fi
echo "[OK] env.default updated to: $(grep -E '^SMA_INTENT_ML_PKL=' scripts/env.default | cut -d= -f2-)"

# 3) 重啟 API（沿用你現有 api_up/down）
[ -x scripts/api_down.sh ] && scripts/api_down.sh || true
[ -x scripts/api_up.sh ] && scripts/api_up.sh || { echo "[FATAL] scripts/api_up.sh 不在"; exit 2; }

# 4) 三路驗證（API 端點）
if [ -x scripts/sanity_all.sh ]; then
  scripts/sanity_all.sh || true
else
  echo "[WARN] scripts/sanity_all.sh 不在，略過 smoke/tri-eval 列印"
fi

# 5) 路徑索引
echo "[*] WHERE API:"; [ -x scripts/api_where.sh ] && scripts/api_where.sh || true
echo "[*] TRAIN+SWAP REPORT: $(cd "$RUN"&&pwd)"

#!/usr/bin/env bash
set -Eeuo pipefail
set -o errtrace
shopt -s inherit_errexit lastpipe
export PS4='+ [${BASH_SOURCE##*/}:${LINENO}] $(date "+%H:%M:%S") ► '

trap 'rc=$?; echo "[TRAP][ERR] line=$LINENO rc=$rc cmd=${BASH_COMMAND}"; exit $rc' ERR
trap 'echo "[TRAP][EXIT] rc=$?"' EXIT

TS="$(date +%F_%H%M%S)"
PROJ="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$PROJ" || { echo "[ERR] project not found: $PROJ"; exit 90; }

# venv
ACT_OK=0
if [ -f .venv/bin/activate ]; then . .venv/bin/activate && ACT_OK=1; fi
if [ $ACT_OK -eq 0 ] && [ -f "$HOME/.venv/sma/bin/activate" ]; then . "$HOME/.venv/sma/bin/activate" && ACT_OK=1; fi
[ $ACT_OK -eq 1 ] || { echo "[ERR] virtualenv not found (.venv or ~/.venv/sma)"; exit 91; }

mkdir -p .sma_tools/logs reports_auto artifacts data/intent

PRJ_LOG=".sma_tools/logs/train_eval_pro_${TS}.log"
TMP_LOG="/tmp/sma_train_eval_pro_${TS}.log"
exec > >(tee -a "$TMP_LOG" | tee -a "$PRJ_LOG") 2>&1
set -x

# 0) Python環境探勘
python -X faulthandler - <<'PY'
import numpy, scipy, sklearn
print(f"[ENV] numpy={numpy.__version__} scipy={scipy.__version__} sklearn={sklearn.__version__}")
PY

# 1) 確保 test clean 檔存在（若已由舊腳本產生就直接用）
TEST_RAW="${1:-downloads/external_realistic_test.jsonl}"
TEST_CLEAN="data/intent/external_realistic_test.clean.jsonl"
if [ ! -f "$TEST_CLEAN" ]; then
  if [ -f "$TEST_RAW" ]; then
    # 簡潔清洗：逐行保留（若為純文字仍可用）
    cp "$TEST_RAW" "$TEST_CLEAN"
    echo "[CLEAN] copied $TEST_RAW -> $TEST_CLEAN"
  else
    echo "[WARN] test file missing: $TEST_RAW ; evaluation will be skipped"
    TEST_CLEAN=""
  fi
fi

# 2) 訓練 + 校準 + 評估
SEED_ENV="${SEED:-42}"
python -X faulthandler .sma_tools/train_pro.py \
  --train "data/intent/i_20250901_merged.jsonl" \
  --test "${TEST_CLEAN}" \
  --model_out "artifacts/intent_pro_cal.pkl" \
  --report_prefix "reports_auto/external" \
  --seed "${SEED_ENV}"

echo
echo "=== PRO REPORT ==="
sed -n '1,200p' reports_auto/external_eval_manual_pro.txt || true

echo
echo "=== PRO CONFUSION ==="
sed -n '1,200p' reports_auto/external_confusion_pro.tsv || true

echo
echo "=== PRO ERRORS (top 20) ==="
sed -n '1,21p' reports_auto/external_errors_pro.tsv || true

echo
echo "[LOG] tmp:  $TMP_LOG"
echo "[LOG] proj: $PRJ_LOG"

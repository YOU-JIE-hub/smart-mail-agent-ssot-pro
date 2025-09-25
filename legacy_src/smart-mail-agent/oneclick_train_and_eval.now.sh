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

# 0) venv
ACT_OK=0
if [ -f .venv/bin/activate ]; then . .venv/bin/activate && ACT_OK=1; fi
if [ $ACT_OK -eq 0 ] && [ -f "$HOME/.venv/sma/bin/activate" ]; then . "$HOME/.venv/sma/bin/activate" && ACT_OK=1; fi
[ $ACT_OK -eq 1 ] || { echo "[ERR] virtualenv not found (.venv or ~/.venv/sma)"; exit 91; }

mkdir -p .sma_tools/logs reports_auto data/intent

# 1) 雙份日誌
PRJ_LOG=".sma_tools/logs/train_eval_${TS}.log"
TMP_LOG="/tmp/sma_train_eval_${TS}.log"
exec > >(tee -a "$TMP_LOG" | tee -a "$PRJ_LOG") 2>&1
set -x

# 2) 列環境
python -X faulthandler - <<'PY'
import numpy, scipy, sklearn
print(f"[ENV] numpy={numpy.__version__} scipy={scipy.__version__} sklearn={sklearn.__version__}")
PY

# 3) 檔案快檢：Python 檔用 py_compile，Shell 檔用 bash -n
python -X faulthandler - <<'PY'
import py_compile
py_files = [
  ".sma_tools/auto_augment_train.py",
  ".sma_tools/calibrate_and_card.py",
  ".sma_tools/route_predict.py",
  ".sma_tools/predict_full.py",
  ".sma_tools/extract_fields.py",
  ".sma_tools/priority_rules.py",
  ".sma_tools/eval_only.py",
]
for f in py_files:
    py_compile.compile(f, doraise=True)
print("[OK] python tools compile")
PY

bash -n .sma_tools/oneclick_eval_external.sh
echo "[OK] shell tool syntax"

# 4) 訓練（可用 TRAIN_ARGS 覆寫）
if [ -z "${TRAIN_ARGS:-}" ]; then TRAIN_ARGS=""; fi
python -X faulthandler .sma_tools/auto_augment_train.py ${TRAIN_ARGS}

# 5) 校準（存在才做）
if [ -f artifacts/intent_svm_plus_auto.pkl ]; then
  python -X faulthandler .sma_tools/calibrate_and_card.py artifacts/intent_svm_plus_auto.pkl \
  || echo "[WARN] calibration failed (skip)"
else
  echo "[WARN] base model missing; skip calibration"
fi

# 6) 外部資料清理+評估
EXT_IN="downloads/external_realistic_test.jsonl"
[ -f "$EXT_IN" ] || { echo "[ERR] not found external set: $EXT_IN"; exit 92; }
bash -x .sma_tools/oneclick_eval_external.sh "$EXT_IN"

# 7) 彙整輸出
echo "[LOG] tmp:  $TMP_LOG"
echo "[LOG] proj: $PRJ_LOG"

echo; echo "=== CHECK ==="
sed -n '1,200p' reports_auto/external_check.txt || true

echo; echo "=== REPORT ==="
sed -n '1,200p' reports_auto/external_eval_manual.txt || true

echo; echo "=== ERRORS (前20) ==="
sed -n '1,21p' reports_auto/external_errors.tsv || true

echo; echo "=== LOG TAIL (proj) ==="
tail -n 120 "$PRJ_LOG" || true

echo; echo "=== LOG TAIL (tmp) ==="
tail -n 120 "$TMP_LOG" || true

echo "[DONE] oneclick train+eval @ $TS"

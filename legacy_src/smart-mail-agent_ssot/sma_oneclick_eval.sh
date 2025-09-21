#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-/home/youjie/projects/smart-mail-agent_ssot}"
cd "$ROOT" || { echo "[FATAL] not found: $ROOT"; exit 2; }
TS="$(date +%Y%m%dT%H%M%S)"
RUN_LOG="reports_auto/logs/EVAL_${TS}.log"
ERR_LOG="reports_auto/logs/EVAL_ERROR_${TS}.log"
PY_ERR="reports_auto/logs/EVAL_${TS}.stderr.log"
DATA="${1:-data/eval_demo}"
echo "[INFO] dataset=$DATA" | tee -a "$RUN_LOG"
[ -f .venv/bin/activate ] && . .venv/bin/activate 2>/dev/null || true
python -m pip -q install -U pip >/dev/null 2>&1 || true
pip -q install "scikit-learn==1.7.1" "pandas>=1.5,<3" "matplotlib>=3.4" >/dev/null 2>&1 || true
set -o pipefail
python scripts/sma_eval_all.py "$DATA" 1>>"$RUN_LOG" 2>>"$PY_ERR" || {
  {
    echo "----- EVAL FAILED -----"
    echo "time: $(date -Is)"
    echo "cmd: python scripts/sma_eval_all.py $DATA"
    echo "--- stderr head ---"; head -n 80 "$PY_ERR" || true
    echo "--- stderr tail ---"; tail -n 80 "$PY_ERR" || true
  } | tee -a "$ERR_LOG"
  TS2="$(date +%Y%m%dT%H%M%S)"
  OUT="reports_auto/errors/EVAL_CRASH_${TS2}"
  mkdir -p "$OUT"
  [[ -s "$ERR_LOG" ]] && cp -f "$ERR_LOG" "$OUT/" || true
  [[ -s "$PY_ERR"  ]] && cp -f "$PY_ERR"  "$OUT/" || true
  [[ -f reports_auto/logs/pipeline.ndjson ]] && tail -n 200 reports_auto/logs/pipeline.ndjson > "$OUT/pipeline_tail.last200.ndjson" || true
  exit 1
}
echo "[OK] Eval 完成，詳見 reports_auto/eval/" | tee -a "$RUN_LOG"

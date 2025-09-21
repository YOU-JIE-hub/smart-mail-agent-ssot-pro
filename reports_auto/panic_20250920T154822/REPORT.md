# Panic Report
- Exit code: 0
- CMD  : 
set -Eeuo pipefail

# 鎖定你指定的 SPAM；INTENT 用既有 pkl（若缺就只算 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - <<'PY'
- LOG  : reports_auto/panic_20250920T154822/run.log
- ERR  : reports_auto/panic_20250920T154822/run.err
- PY   : reports_auto/panic_20250920T154822/python_stderr.txt
- OOM  : reports_auto/panic_20250920T154822/oom.txt
- TRACE: reports_auto/panic_20250920T154822/xtrace.sh
- SYS  : reports_auto/panic_20250920T154822/system.txt

## Heuristics

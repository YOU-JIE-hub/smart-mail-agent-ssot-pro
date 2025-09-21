+ CMD='
set -Eeuo pipefail

# 鎖定你指定的 SPAM；INTENT 用既有 pkl（若缺就只算 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - <<'\''PY'\'''
+ '[' -z '
set -Eeuo pipefail

# 鎖定你指定的 SPAM；INTENT 用既有 pkl（若缺就只算 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - <<'\''PY'\''' ']'
+ echo '== SNAPSHOT 20250920T154822 =='
+ pwd
+ uname -a
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ env
+ grep -E 'INTENT_PKL|SPAM_PKL|KIE_DIR|PYTHONPATH'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc '
set -Eeuo pipefail

# 鎖定你指定的 SPAM；INTENT 用既有 pkl（若缺就只算 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - <<'\''PY'\'''
++ tee -a reports_auto/panic_20250920T154822/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : 
set -Eeuo pipefail

# 鎖定你指定的 SPAM；INTENT 用既有 pkl（若缺就只算 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - <<'\''PY'\'''
+ echo '- LOG  : reports_auto/panic_20250920T154822/run.log'
+ echo '- ERR  : reports_auto/panic_20250920T154822/run.err'
+ echo '- PY   : reports_auto/panic_20250920T154822/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250920T154822/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T154822/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250920T154822/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'only one class' reports_auto/panic_20250920T154822/run.err reports_auto/panic_20250920T154822/python_stderr.txt
+ grep -qi 'No module named '\''tools'\''' reports_auto/panic_20250920T154822/run.err reports_auto/panic_20250920T154822/python_stderr.txt
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250920T154822/run.err reports_auto/panic_20250920T154822/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250920T154822/run.err reports_auto/panic_20250920T154822/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T154822/oom.txt
+ echo
+ echo '=== DIAG OUTPUTS ==='
+ printf '%s\n' reports_auto/panic_20250920T154822/REPORT.md reports_auto/panic_20250920T154822/run.log reports_auto/panic_20250920T154822/run.err reports_auto/panic_20250920T154822/python_stderr.txt reports_auto/panic_20250920T154822/xtrace.sh reports_auto/panic_20250920T154822/system.txt reports_auto/panic_20250920T154822/oom.txt
+ echo
+ exit 0

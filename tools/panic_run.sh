set -Eeuo pipefail
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/panic_${TS}"; mkdir -p "$OUT"
LOG="$OUT/run.log"; ERR="$OUT/run.err"; PYERR="$OUT/python_stderr.txt"
TRACE="$OUT/xtrace.sh"; SYS="$OUT/system.txt"; OOMS="$OUT/oom.txt"; REP="$OUT/REPORT.md"

# 落所有輸出
exec > >(tee -a "$LOG") 2> >(tee -a "$ERR" >&2)
export PYTHONFAULTHANDLER=1 PYTHONWARNINGS=default PYTHONUNBUFFERED=1 PYTHONHASHSEED=0
export PYTHONPATH="$PWD:${PYTHONPATH:-}"

# 先開 FD 再 set -x（避免 invalid value）
exec 5> "$TRACE"; export BASH_XTRACEFD=5; set -x

CMD="${*:-}"
if [ -z "$CMD" ]; then
  echo "[FATAL] no CMD. 用法：bash tools/panic_run.sh '<你的指令>'" | tee -a "$ERR"
  exit 64
fi

# 系統快照
{
  echo "== SNAPSHOT ${TS} =="; pwd
  uname -a || true
  python3 -V || true; pip -V || true
  which -a python3 || true
  free -h || true
  df -h . || true
  ulimit -a || true
  env | grep -E 'INTENT_PKL|SPAM_PKL|KIE_DIR|PYTHONPATH' || true
} > "$SYS" 2>&1

# 事前 dmesg (OOM 線索)
dmesg 2>/dev/null | egrep -i 'killed process|out of memory|oom' | tail -n 120 > "$OOMS" || true

# 執行
set +e
timeout --preserve-status 3h bash -lc "$CMD" 2> >(tee -a "$PYERR" >&2)
ec=$?
set -e

# 事後 dmesg (OOM 線索)
{
  echo "== dmesg tail (OOM related) ==";
  dmesg 2>/dev/null | egrep -i 'killed process|out of memory|oom' | tail -n 120 || true
} >> "$OOMS" 2>&1

# 快速結論
{
  echo "# Panic Report"
  echo "- Exit code: ${ec}"
  echo "- CMD  : $CMD"
  echo "- LOG  : $LOG"
  echo "- ERR  : $ERR"
  echo "- PY   : $PYERR"
  echo "- OOM  : $OOMS"
  echo "- TRACE: $TRACE"
  echo "- SYS  : $SYS"
  echo
  echo "## Heuristics"
  grep -qi "only one class" "$ERR" "$PYERR" 2>/dev/null && echo "- 單一類別切分（資料/切折不平衡）"
  grep -qi "No module named 'tools'" "$ERR" "$PYERR" 2>/dev/null && echo "- 模組路徑：已固定加 PYTHONPATH=\$PWD"
  grep -qi "Can't get attribute 'rules_feat" "$ERR" "$PYERR" 2>/dev/null && echo "- 舊 .pkl 需要 __main__.rules_feat*（反序列化相容性）"
  grep -qi 'Killed' "$ERR" "$PYERR" 2>/dev/null && echo "- 可能 OOM 被系統殺掉"
  grep -qi 'out of memory' "$OOMS" 2>/dev/null && echo "- dmesg 有 OOM"
  grep -qi 'No such file or directory' "$ERR" "$PYERR" 2>/dev/null && echo "- 路徑不存在"
  grep -qi 'Permission denied' "$ERR" "$PYERR" 2>/dev/null && echo "- 權限問題"
} > "$REP"

set +x
echo
echo "=== DIAG OUTPUTS ==="
printf "%s\n" "$REP" "$LOG" "$ERR" "$PYERR" "$TRACE" "$SYS" "$OOMS"
echo
exit "$ec"

set -Eeuo pipefail
TS="$(date +%Y%m%dT%H%M%S)"; OUT="reports_auto/panic_${TS}"; mkdir -p "$OUT"
LOG="$OUT/run.log"; ERR="$OUT/run.err"; TRACE="$OUT/xtrace.sh"
SYS="$OUT/system.txt"; PYERR="$OUT/python_stderr.txt"; OOMS="$OUT/oom.txt"; REP="$OUT/REPORT.md"
exec > >(tee -a "$LOG") 2> >(tee -a "$ERR" >&2)
export PYTHONFAULTHANDLER=1 PYTHONUNBUFFERED=1 PYTHONWARNINGS=default PYTHONHASHSEED=0
export PYTHONPATH="$PWD:${PYTHONPATH:-}"
exec 5> "$TRACE"; export BASH_XTRACEFD=5; set -x
CMD="${*:-}"; [ -z "$CMD" ] && echo "[FATAL] no CMD" | tee -a "$ERR" && exit 64
{ echo "== SNAPSHOT ${TS} =="; pwd; python3 -V || true; pip -V || true; which -a python3 || true
  free -h || true; df -h . || true; ulimit -a || true
  env | grep -E 'INTENT|SPAM|PYTHONPATH' || true; } > "$SYS" 2>&1
dmesg 2>/dev/null | egrep -i 'killed process|out of memory|oom' | tail -n 120 > "$OOMS" || true
set +e; timeout --preserve-status 3h bash -lc "$CMD" 2> >(tee -a "$PYERR" >&2); ec=$?; set -e
{ echo "== dmesg tail (OOM related) =="; dmesg 2>/dev/null | egrep -i 'killed process|out of memory|oom' | tail -n 120 || true; } >> "$OOMS" 2>&1
{ echo "# Panic Report"; echo "- Exit code: ${ec}"; echo "- CMD  : $CMD"
  echo "- LOG  : $LOG"; echo "- ERR  : $ERR"; echo "- PY   : $PYERR"
  echo "- OOM  : $OOMS"; echo "- TRACE: $TRACE"; echo "- SYS  : $SYS"; echo; echo "## Heuristics"
  grep -qi "JSONDecodeError" "$ERR" "$PYERR" 2>/dev/null && echo "- JSON 格式壞/不是 JSONL"
  grep -qi "Permission denied" "$ERR" "$PYERR" 2>/dev/null && echo "- 權限問題"
  grep -qi "Killed" "$ERR" "$PYERR" 2>/dev/null && echo "- 可能 OOM 被系統殺掉"
  grep -qi "only one class" "$ERR" "$PYERR" 2>/dev/null && echo "- 只有單一類別（資料切分有誤）"
} > "$REP"
echo -e "\n=== DIAG OUTPUTS ===\n$REP\n$LOG\n$ERR\n$PYERR\n$TRACE\n$SYS\n$OOMS\n"
exit "$ec"

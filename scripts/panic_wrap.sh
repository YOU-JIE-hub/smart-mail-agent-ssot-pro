#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $# -lt 1 ]]; then echo "Usage: $0 '<command>' [label]" >&2; exit 2; fi
CMD="$1"
LABEL="${2:-run}"
safe_label="$(printf "%s" "$LABEL" | sed 's/[^A-Za-z0-9._:-]/_/g')"
PANIC_ROOT="reports_auto"
mkdir -p "$PANIC_ROOT"
ts="$(date -u +%Y%m%dT%H%M%S)"
dir="$PANIC_ROOT/panic_${ts}_${safe_label}"
mkdir -p "$dir"
echo "[PANIC] DIR: $dir"

# 系統資訊
{ 
  echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)";
  echo "cwd: $PWD";
  echo; echo "=== uname -a ==="; uname -a || true;
  echo; echo "=== python --version ==="; python --version || true;
  echo; echo "=== pip freeze (top 50) ==="; pip freeze 2>/dev/null | head -50 || true;
} >"$dir/system.txt" 2>&1

# 以 xtrace 追蹤並將 stdout/stderr 分流落檔；stderr 也複本到 xtrace.sh
rc=0
( set -Eeuo pipefail; set -x; bash -lc "$CMD" ) \
  > >(tee "$dir/raw.out") \
  2> >(tee "$dir/raw.err" "$dir/xtrace.sh" >&2) || rc=$?

# 整理 run.log / run.err
cat "$dir/raw.out" > "$dir/run.log" 2>/dev/null || true
if [[ $rc -ne 0 ]]; then
  {
    echo "CMD: $CMD"
    echo "EXIT: $rc"
    echo; echo "=== STDERR (tail) ==="
    tail -n 200 "$dir/raw.err" 2>/dev/null || true
    echo; echo "=== XTRACE (tail) ==="
    tail -n 200 "$dir/xtrace.sh" 2>/dev/null || true
  } >"$dir/run.err"
else
  : >"$dir/run.err"
fi

# REPORT.md
{
  echo "# Panic Report"
  echo
  echo "- dir: $dir"
  echo "- cmd: $CMD"
  echo "- exit: $rc"
  echo
  echo "## Files"
  echo "- raw.out / raw.err: 原始輸出"
  echo "- run.log: stdout 彙整"
  echo "- run.err: 失敗時的摘要（含 tail）"
  echo "- xtrace.sh: set -x 追蹤"
  echo "- system.txt: 系統/環境"
} >"$dir/REPORT.md"

echo "$dir"  # 讓呼叫端能抓到目錄路徑
exit $rc

#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $# -lt 1 ]]; then echo "Usage: $0 '<command>' [label]" >&2; exit 2; fi
CMD="$1"
LABEL="${2:-run}"
safe_label="$(printf "%s" "$LABEL" | sed 's/[^A-Za-z0-9._:-]/_/g')"
PANIC_ROOT="reports_auto"; mkdir -p "$PANIC_ROOT"
_before="$(ls -1dt "$PANIC_ROOT"/panic_* 2>/dev/null | head -1 || true)"
_work="$(mktemp -d)"
if [[ -x tools/panic.sh ]]; then
  bash tools/panic.sh "$CMD" >"$_work/out.txt" 2>&1 || true
else
  bash -lc "$CMD" >"$_work/out.txt" 2>&1 || true
fi
_after="$(ls -1dt "$PANIC_ROOT"/panic_* 2>/dev/null | head -1 || true)"
if [[ -n "$_after" && "$_after" != "$_before" ]]; then
  dir="$_after"
else
  ts="$(date -u +%Y%m%dT%H%M%S)"; dir="$PANIC_ROOT/panic_${ts}_${safe_label}"
  mkdir -p "$dir"
  cp -f "$_work/out.txt" "$dir/raw.out" || true
  cp -f "$_work/out.txt" "$dir/run.log" || true
  grep -iE "error|traceback|exception|failed|fatal" "$_work/out.txt" >"$dir/run.err" || true
  {
    echo "# Panic report"
    echo "label: $LABEL"
    echo "cmd: $CMD"
    echo
    echo "## tail -n 100 raw.out"
    tail -n 100 "$_work/out.txt" || true
  } >"$dir/REPORT.md"
fi
echo "$dir"

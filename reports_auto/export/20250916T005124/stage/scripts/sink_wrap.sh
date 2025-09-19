#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"; mkdir -p "$ERR_DIR"
TS="$(date +%Y%m%dT%H%M%S)"; RUN="reports_auto/wrap/${TS}"; mkdir -p "$RUN"
LOG="$RUN/run.log"; E="$RUN/wrap.err"; PY="$RUN/py_last_trace.txt"
exec > >(tee -a "$LOG") 2>&1
copy(){ local s="${1:-}"; local d="${2:-}"; [ -n "$s" ] && [ -f "$s" ] && cp -f "$s" "$d" || true; }
sink(){ copy "$1" "$ERR_DIR/api.err"; copy "$LOG" "$ERR_DIR/run.log"; copy "$2" "$ERR_DIR/py_last_trace.txt"; copy "$3" "$ERR_DIR/server.log"; (cd "$RUN"&&pwd)|awk '{print "RUN_DIR="$0}' > "$ERR_DIR/where.txt"; ln -sfn "$(cd "$RUN"&&pwd)" "$ERR_DIR/LATEST_RUN" || true; }
paths(){ echo "[PATHS]"; echo "  RUN_DIR=$(cd "$RUN"&&pwd)"; echo "  LOG=$(cd "$RUN"&&pwd)/run.log"; echo "  ERR=$(cd "$RUN"&&pwd)/wrap.err"; echo "  PY_LAST=$(cd "$RUN"&&pwd)/py_last_trace.txt"; }
on_err(){ ec=${1:-$?}; echo "exit_code=$ec" > "$E"; sink "$E" "$PY" ""; paths; exit 0; }
on_exit(){ copy "$LOG" "$ERR_DIR/run.log"; (cd "$RUN"&&pwd)|awk '{print "RUN_DIR="$0}' > "$ERR_DIR/where.txt"; ln -sfn "$(cd "$RUN"&&pwd)" "$ERR_DIR/LATEST_RUN" || true; paths; }
trap 'on_err $?' ERR; trap on_exit EXIT
[ $# -eq 0 ] && { echo "[FATAL] need command"; exit 0; }
bash -x -o pipefail -c "$*" || on_err $?

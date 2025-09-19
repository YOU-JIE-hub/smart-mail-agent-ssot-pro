#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="${ROOT:-/home/youjie/projects/smart-mail-agent-ssot-pro}"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"; mkdir -p "$ERR_DIR"

print_paths(){ echo "[PATHS]"; echo "  RUN_DIR=$RUN_DIR"; echo "  LOG=$LOG"; echo "  ERR=$ERR"; echo "  PY_LAST=$PY_LAST"; }
error_sink::copy(){ local src="$1" dst="$2"; [ -n "$src" ] && [ -f "$src" ] && cp -f "$src" "$dst" || true; }
sink_err(){ local d="$1" e="$2" py="$3"; mkdir -p "$ERR_DIR"; error_sink::copy "$e" "$ERR_DIR/api.err"; error_sink::copy "$d/run.log" "$ERR_DIR/run.log"; error_sink::copy "$py" "$ERR_DIR/py_last_trace.txt"; ln -sfn "$(cd "$d" && pwd)" "$ERR_DIR/LATEST_RUN"; }
sink_run(){ local d="$1"; error_sink::copy "$d/run.log" "$ERR_DIR/run.log"; ln -sfn "$(cd "$d" && pwd)" "$ERR_DIR/LATEST_RUN"; }

TS="$(date +%Y%m%dT%H%M%S)"
RUN_DIR="$ROOT/reports_auto/wrap/${TS}"; LOG="$RUN_DIR/run.log"; ERR="$RUN_DIR/wrap.err"; PY_LAST="$RUN_DIR/py_last_trace.txt"
mkdir -p "$RUN_DIR"
exec > >(tee -a "$LOG") 2>&1

on_err(){ ec=${1:-$?}; echo "=== BASH_TRAP(sink_wrap) ===" >>"$ERR"; echo "TIME: $(date -Is)" >>"$ERR"; echo "LAST:${BASH_COMMAND:-<none>}" >>"$ERR"; echo "CODE:$ec" >>"$ERR"; echo "exit_code=$ec" >>"$ERR"; sink_err "$RUN_DIR" "$ERR" "$PY_LAST"; print_paths; exit "$ec"; }
on_exit(){ sink_run "$RUN_DIR"; print_paths; }
trap 'on_err $?' ERR; trap on_exit EXIT

[ $# -eq 0 ] && { echo "[FATAL] usage: scripts/sink_wrap.sh <command...>"; exit 2; }
"$@"

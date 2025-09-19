#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
RUN="$(ls -1dt reports_auto/api/2* 2>/dev/null | head -n1 || true)"; [ -n "$RUN" ] || { echo "[FATAL] no api run dir"; exit 2; }
echo "RUN_DIR=$(cd "$RUN"&&pwd)"; echo "LOG=$(cd "$RUN"&&pwd)/run.log"; echo "ERR=$(cd "$RUN"&&pwd)/api.err"; echo "PY_LAST=$(cd "$RUN"&&pwd)/py_last_trace.txt"
[ -f "$RUN/server.log" ] && echo "SERVER=$(cd "$RUN"&&pwd)/server.log"

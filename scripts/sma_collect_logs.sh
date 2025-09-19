#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"
echo "----- COLLECT $(date '+%F %T') -----"
echo "[PORTS]"; ss -ltnp 2>/dev/null | sed -n '1,200p' || true
echo "[PS] api_server.py"; pgrep -a -f api_server.py || true
LAST="$(ls -1dt reports_auto/api/2* 2>/dev/null | head -n1 || true)"
if [ -n "$LAST" ]; then
  echo "[RUN_DIR] $LAST"; echo "[actual_port] $(cat "$LAST/actual_port" 2>/dev/null || echo NA)"
  echo "[HEAD api.out]"; sed -n '1,120p' "$LAST/api.out" 2>/dev/null || true
  echo "[HEAD api.err]"; sed -n '1,120p' "$LAST/api.err" 2>/dev/null || true
fi
echo "[TAIL server.log]"; tail -n 200 "$ERR_DIR/server.log" 2>/dev/null || true
echo "[TAIL run.log]"; tail -n 200 "$ERR_DIR/run.log" 2>/dev/null || true
echo "[CAT api.err]"; cat "$ERR_DIR/api.err" 2>/dev/null || true
echo "[TAIL py_last_trace.txt]"; tail -n 200 "$ERR_DIR/py_last_trace.txt" 2>/dev/null || true

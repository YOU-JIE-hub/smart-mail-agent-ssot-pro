#!/usr/bin/env bash
set -Eeo pipefail
ROOT="$HOME/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
RUN_DIR="reports_auto/api/legacy_${TS}"
mkdir -p "$RUN_DIR" reports_auto/ERR
nohup python -u tools/api_server.py > "$RUN_DIR/api.out" 2> "$RUN_DIR/api.err" &
echo $! > "$RUN_DIR/api.pid"
# 等待 8088 起來（最多 12s）
ok=""
for i in $(seq 1 60); do
  ss -ltn 2>/dev/null | grep -q ":8088\b" && { ok="8088"; break; }
  sleep 0.2
done
echo "${ok:-NA}" > "$RUN_DIR/actual_port"
ln -sfn "$RUN_DIR" reports_auto/api/LATEST 2>/dev/null || true
if [ -n "$ok" ]; then
  echo "[API] http://127.0.0.1:${ok} pid=$(cat "$RUN_DIR/api.pid")"
else
  echo "[FATAL] API not listening on 8088"; exit 87
fi

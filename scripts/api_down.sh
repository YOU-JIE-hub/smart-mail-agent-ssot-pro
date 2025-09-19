#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
PIDFILE="$(ls -1dt reports_auto/api/2*/api.pid 2>/dev/null | head -n1 || true)"
[ -n "${PIDFILE:-}" ] && [ -f "$PIDFILE" ] && { kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE"; }
fuser -k -n tcp 8000 2>/dev/null || true
fuser -k -n tcp 8088 2>/dev/null || true
echo "[*] api_down done"

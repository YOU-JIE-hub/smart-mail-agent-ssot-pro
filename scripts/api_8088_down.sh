#!/usr/bin/env bash
set -Eeo pipefail
ROOT="$HOME/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
LAST="$(ls -1dt reports_auto/api/legacy_* 2>/dev/null | head -n1 || true)"
if [ -n "$LAST" ] && [ -f "$LAST/api.pid" ]; then
  kill "$(cat "$LAST/api.pid")" 2>/dev/null || true
fi
fuser -k -n tcp 8088 2>/dev/null || true
echo "[*] api_8088_down done"

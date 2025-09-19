#!/usr/bin/env bash
set -euo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT"
echo "[CRASH] last files:"
ls -1t reports_auto/logs/CRASH_*.log 2>/dev/null | head -n 3 || true
echo
f="$(ls -1t reports_auto/logs/CRASH_*.log 2>/dev/null | head -n1 || true)"
if [[ -n "${f:-}" && -f "$f" ]]; then
  echo "--- tail -n 400 $f ---"
  tail -n 400 "$f"
fi
echo
if [[ -f reports_auto/logs/pipeline.ndjson ]]; then
  echo "--- tail -n 80 pipeline.ndjson ---"
  tail -n 80 reports_auto/logs/pipeline.ndjson
fi

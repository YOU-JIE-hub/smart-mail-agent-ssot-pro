#!/usr/bin/env bash
set -euo pipefail
p="reports_auto/logs/LAST_CRASH_PATH.txt"
if [ -f "$p" ]; then cat "$p"; else echo "NONE"; fi

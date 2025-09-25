#!/usr/bin/env bash
set -Eeuo pipefail
source .sma_tools/env_guard.sh
[[ $# -gt 0 ]] || { echo "用法：scripts/sma_run.sh <command> [args...]"; exit 64; }
exec "$@"

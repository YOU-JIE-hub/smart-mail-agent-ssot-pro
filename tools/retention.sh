#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
DIR="${1:-reports_auto/online}"
KEEP="${KEEP:-20}"
[ -d "$DIR" ] || exit 0
mapfile -t all < <(ls -1dt "$DIR"/*/ 2>/dev/null || true)
cnt="${#all[@]}"
if (( cnt > KEEP )); then
  for ((i=KEEP;i<cnt;i++)); do rm -rf "${all[$i]}" || true; done
fi

#!/usr/bin/env bash
set -Eeuo pipefail; umask 022

LAST="$(ls -1dt reports_auto/online/* 2>/dev/null | head -n1 || true)"
echo "LATEST: ${LAST:-<none>}"
[ -n "$LAST" ] && { echo "== ls -l $LAST =="; ls -l "$LAST"; }

echo "== port 18080 pids =="
( command -v fuser >/dev/null && fuser 18080/tcp ) || (ps aux | grep -E "uvicorn .*:18080" | grep -v grep || true)

if [ -n "$LAST" ]; then
  echo "== codes =="
  for x in readyz debug_models intent spam kie; do
    printf "%-14s %s\n" "$x" "$(cat "$LAST/$x.code" 2>/dev/null || echo NA)"
  done
  echo "== errors tail =="
  [ -s "$LAST/uvicorn.err" ] && tail -n 120 "$LAST/uvicorn.err" || echo "<no uvicorn.err>"
fi

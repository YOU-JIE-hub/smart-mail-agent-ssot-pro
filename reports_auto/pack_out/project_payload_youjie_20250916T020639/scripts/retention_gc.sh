#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="${ROOT:-/home/youjie/projects/smart-mail-agent-ssot-pro}"; cd "$ROOT"; DAYS="${RETENTION_DAYS:-7}"
now="$(date +%s)"
find reports_auto -type d -regex '.*/[0-9]{8}T[0-9]{6}$' -print0 | while IFS= read -r -d '' d; do
  m="$(date -r "$d" +%s 2>/dev/null || echo 0)"; age=$(( (now - m)/86400 ))
  if [ "$age" -gt "$DAYS" ]; then echo "[GC] rm -rf $d (age=${age}d)"; rm -rf "$d"; fi
done
echo "[OK] GC done"

#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
L="$ROOT/reports_auto/online/latest"
if [ -L "$L" ] || [ -d "$L" ]; then R="$(readlink -f "$L" || echo "$L")"; echo "LATEST: $R"; ls -1 "$R" | sort
else echo "[WARN] no reports_auto/online/latest yet" >&2; fi
